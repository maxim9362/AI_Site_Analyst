// Demo site JavaScript — intercepts form submit without sending data.
document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('contact-form');
    var success = document.getElementById('form-success');
    if (!form || !success) return;

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        form.style.display = 'none';
        success.style.display = '';
    });
});
