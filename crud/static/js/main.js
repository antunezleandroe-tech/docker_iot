const btnDelete = document.querySelectorAll('.btn-borrar');
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
    const themeStylesheet = document.getElementById('theme-stylesheet');

    if (!selectorTema || !themeStylesheet) return;

    // 1. Obtener el tema guardado o usar 'cosmo' por defecto
    const temaActual = localStorage.getItem('tema-crud') || 'cosmo';

    // 2. Aplicar el tema (cambiar la URL del CSS) al abrir la página
    themeStylesheet.href = `https://bootswatch.com/5/${temaActual}/bootstrap.min.css`;
    selectorTema.value = temaActual;

    // 3. Escuchar cambios en el selector
    selectorTema.addEventListener('change', function() {
        const temaSeleccionado = this.value;
        
        // Cambiar el href del link al nuevo tema de Bootswatch
        themeStylesheet.href = `https://bootswatch.com/5/${temaSeleccionado}/bootstrap.min.css`;
        
        // Guardar la nueva preferencia
        localStorage.setItem('tema-crud', temaSeleccionado);
    });
});