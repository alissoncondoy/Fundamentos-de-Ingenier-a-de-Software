(function () {
  function sync(label, input) {
    if (!label || !input) return;
    label.classList.toggle('is-checked', !!input.checked);
  }

  function init() {
    // Soporta ambos casos:
    //  - wrapper del template: .tt-weekdays
    //  - render directo del widget de Django: #id_dias_semana
    document.querySelectorAll('.tt-weekdays, #id_dias_semana').forEach(function (container) {
      container.querySelectorAll('input[type="checkbox"]').forEach(function (input) {
        // Caso 1: input dentro del label (render default de Django)
        // Caso 2: input y label hermanos con atributo for (nuestro widget circular)
        var label = input.closest('label') || container.querySelector('label[for="' + input.id + '"]');
        if (!label) return;

        // Estado inicial
        sync(label, input);

        // Cambio
        input.addEventListener('change', function () {
          sync(label, input);
        });

        // Foco (opcional)
        input.addEventListener('focus', function () {
          label.classList.add('is-focus');
        });
        input.addEventListener('blur', function () {
          label.classList.remove('is-focus');
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
