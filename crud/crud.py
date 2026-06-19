from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os, logging
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
import paho.mqtt.client as mqtt
import ssl
import json

# Configuración básica para registrar eventos y errores en la consola.
logging.basicConfig(format='%(asctime)s - CRUD - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)

# Configuramos ProxyFix para que Flask entienda que está detrás de un proxy reverso (SWAG).
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

# Variables de entorno extraídas de Docker para la base de datos y seguridad.
app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config["MYSQL_USER"] = os.environ["MYSQL_USER"]
app.config["MYSQL_PASSWORD"] = os.environ["MYSQL_PASSWORD"]
app.config["MYSQL_DB"] = os.environ["MYSQL_DB"]
app.config["MYSQL_HOST"] = os.environ["MYSQL_HOST"]
app.config['PERMANENT_SESSION_LIFETIME']=180
mysql = MySQL(app)

# Variables de configuración para la conexión con el broker MQTT.
MQTT_BROKER = "leandroezz.duckdns.org"
MQTT_PORT = 18205
MQTT_USER = os.environ.get("MQTT_USR", "root") 
MQTT_PASS = os.environ.get("MQTT_PASS", "") 


# SECCIÓN 1: AGENDA (CRUD DE CONTACTOS Y AUTENTICACIÓN).
# Aquí agrupamos todas las rutas que manejan la base de datos MySQL.

# Decorador personalizado para proteger las rutas. 
# Si el usuario no está logueado, lo redirige al login.
def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta para registrar nuevos usuarios en el sistema.
@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":

        if not request.form.get("usuario"):
            return "el campo usuario es oblicatorio"

        elif not request.form.get("password"):
            return "el campo contraseña es oblicatorio"

        # Generamos un hash seguro de la contraseña antes de guardarla en la BD.
        passhash=generate_password_hash(request.form.get("password"), method='scrypt', salt_length=16)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO usuarios (usuario, hash) VALUES (%s,%s)", (request.form.get("usuario"), passhash[17:]))
        
        if mysql.connection.affected_rows():
            flash('Se agregó un usuario') 
            logging.info("se agregó un usuario")
        mysql.connection.commit()
        return redirect(url_for('index'))

    return render_template('registrar.html')

# Ruta para iniciar sesión. Compara el hash de la BD con la contraseña ingresada.
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not request.form.get("usuario"):
            return "el campo usuario es oblicatorio"
        elif not request.form.get("password"):
            return "el campo contraseña es oblicatorio"

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario LIKE %s", (request.form.get("usuario"),))
        rows=cur.fetchone()
        
        if(rows):
            if (check_password_hash('scrypt:32768:8:1$' + rows[2],request.form.get("password"))):
                session.permanent = True
                session["user_id"]=request.form.get("usuario")
                logging.info("se autenticó correctamente")
                return redirect(url_for('index'))
            else:
                flash('usuario o contraseña incorrecto')
                return redirect(url_for('login'))
    return render_template('login.html')

# Ruta principal del CRUD. Muestra la tabla con todos los contactos guardados.
@app.route('/')
@require_login
def index():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM contactos')
    datos = cur.fetchall()
    cur.close()
    return render_template('index.html', contactos = datos)

# Ruta para procesar el formulario de creación de un nuevo contacto.
@app.route('/add_contact', methods=['POST'])
@require_login
def add_contact():
    if request.method == 'POST':
        nombre = request.form['nombre']
        tel = request.form['tel']
        email = request.form['email']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO contactos (nombre, tel, email) VALUES (%s,%s,%s)"
                    , (nombre, tel, email))
        if mysql.connection.affected_rows():
            flash('Se agregó un contacto') 
            logging.info("se agregó un contacto")
            mysql.connection.commit()
    return redirect(url_for('index'))

# Ruta para eliminar un contacto específico mediante su ID.
@app.route('/borrar/<string:id>', methods = ['GET'])
@require_login
def borrar_contacto(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM contactos WHERE id = %s', (id,))
    if mysql.connection.affected_rows():
        flash('Se eliminó un contacto') 
        logging.info("se eliminó un contacto")
        mysql.connection.commit()
    return redirect(url_for('index'))

# Ruta para cargar los datos de un contacto en el formulario de edición.
@app.route('/editar/<id>', methods = ['GET'])
@require_login
def conseguir_contacto(id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM contactos WHERE id = %s', (id,))
    datos = cur.fetchone()
    logging.info(datos)
    return render_template('editar-contacto.html', contacto = datos)

# Ruta para guardar los cambios realizados en un contacto existente.
@app.route('/actualizar/<id>', methods=['POST'])
@require_login
def actualizar_contacto(id):
    if request.method == 'POST':
        nombre = request.form['nombre']
        tel = request.form['tel']
        email = request.form['email']
        cur = mysql.connection.cursor()
        cur.execute("UPDATE contactos SET nombre=%s, tel=%s, email=%s WHERE id=%s", (nombre, tel, email, id))
    if mysql.connection.affected_rows():
        flash('Se actualizó un contacto') 
        logging.info("se actualizó un contacto")
        mysql.connection.commit()
    return redirect(url_for('index'))

# Ruta para cerrar la sesión activa del usuario y limpiar las variables de sesión.
@app.route("/logout")
@require_login
def logout():
    session.clear()
    logging.info("el usuario {} cerró su sesión".format(session.get("user_id")))
    return redirect(url_for('index'))


# SECCIÓN 2: CONTROL DE NODOS (RASPBERRY PI PICO).
# Aquí agrupamos la lógica de IoT y comunicación con el broker MQTT.

# Función auxiliar diseñada para aislar la lógica de conexión MQTT.
# Se encarga de empaquetar los datos y enviarlos de forma segura.
def enviar_comando_mqtts(topico, payload_dict):
    try:
        cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="flask_crud_web")
        cliente.username_pw_set(MQTT_USER, MQTT_PASS)
        
        # Implementamos TLS/SSL para cumplir con el requisito de MQTTS.
        context = ssl.create_default_context()
        cliente.tls_set_context(context)
        
        cliente.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Convertimos el diccionario de Python a un string JSON para el envío.
        payload_json = json.dumps(payload_dict)
        cliente.publish(topico, payload_json, qos=1)
        
        cliente.disconnect()
        
        logging.info(f"Comando enviado a {topico}: {payload_json}")
        return True, "Comando enviado exitosamente por MQTTS."
        
    except Exception as e:
        logging.error(f"Error MQTTS: {str(e)}")
        return False, f"Error de conexión MQTT: {str(e)}"

# Ruta que renderiza la interfaz web de control y procesa los comandos enviados.
@app.route('/control_pico', methods=['GET', 'POST'])
#@require_login  
def control_pico():
    if request.method == 'POST':
        # Capturamos los datos enviados desde el formulario HTML.
        nodo = request.form.get('nodo')
        instruccion = request.form.get('instruccion')
        
        if not nodo or not instruccion:
            flash("Error: Faltan datos en el formulario.")
            return redirect(url_for('control_pico'))
            
        # Armamos dinámicamente el tópico concatenando el nombre del nodo.
        topico_destino = f"{nodo}/comandos"
        payload = {"comando": instruccion}
        
        # Si la instrucción es cambiar el setpoint, agregamos el valor numérico al JSON.
        if instruccion == 'setpoint':
            valor = request.form.get('valor_setpoint')
            if valor:
                payload["valor"] = float(valor)
            else:
                flash("Error: Debes ingresar un valor para el setpoint.")
                return redirect(url_for('control_pico'))
                
        # Invocamos la función auxiliar para ejecutar la transmisión.
        exito, msj_resultado = enviar_comando_mqtts(topico_destino, payload)
        flash(msj_resultado)
        return redirect(url_for('control_pico'))

    return render_template('control_pico.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)