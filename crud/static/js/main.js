
const btnDelete= document.querySelectorAll('.btn-borrar');
if(btnDelete) {
  const btnArray = Array.from(btnDelete);
  btnArray.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      if(!confirm('¿Está seguro de querer borrar?')){
        e.preventDefault();
      }
    });
  })
}
document.addEventListener('DOMContentLoaded', () => {
    const selectorTema = document.getElementById('selectorTema');

    // Si el selector no existe en el DOM (usuario no logueado), detenemos la ejecución
    if (!selectorTema) return;

    // 1. Obtener el tema guardado en localStorage o usar 'light' por defecto
    const temaActual = localStorage.getItem('tema-crud') || 'light';

    // 2. Aplicar el tema al abrir la página y sincronizar el selector
    document.documentElement.setAttribute('data-theme', temaActual);
    selectorTema.value = temaActual;

    // 3. Escuchar cuando el usuario cambie la opción en el selector desplegable
    selectorTema.addEventListener('change', function() {
        const temaSeleccionado = this.value;
        
        // Cambiar el atributo en el HTML
        document.documentElement.setAttribute('data-theme', temaSeleccionado);
        
        // Guardar la nueva preferencia en el navegador
        localStorage.setItem('tema-crud', temaSeleccionado);
    });
});
