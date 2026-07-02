document.addEventListener('DOMContentLoaded', function() {
    // Копируем embed-код по клику, чтобы клиент мог быстро вставить tracker на сайт.
    var codeBlocks = document.querySelectorAll('.code-block');
    codeBlocks.forEach(function(block) {
        block.style.cursor = 'pointer';
        block.title = 'Нажмите, чтобы скопировать';
        block.addEventListener('click', function() {
            var code = block.querySelector('code');
            if (code) {
                navigator.clipboard.writeText(code.textContent).then(function() {
                    var originalText = code.textContent;
                    code.textContent = 'Скопировано!';
                    setTimeout(function() {
                        code.textContent = originalText;
                    }, 1500);
                });
            }
        });
    });

    // Запускаем MVP-действия прямо из админки: сбор знаний, классификацию и генерацию отчета.
    var actionButtons = document.querySelectorAll('[data-admin-action]');
    actionButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            runAdminAction(button);
        });
    });
});

function runAdminAction(button) {
    var panel = button.closest('.action-panel');
    var status = panel ? panel.querySelector('.admin-action-status') : null;
    var endpoints = getActionEndpoints(button);

    if (!endpoints.length) {
        setActionStatus(status, 'Не найден API-эндпоинт для действия.', true);
        return;
    }

    setButtonsDisabled(panel, true);
    setActionStatus(status, 'Выполняю...', false);

    runEndpointSequence(endpoints)
        .then(function(results) {
            setActionStatus(status, buildSuccessMessage(results), false);
            setTimeout(function() {
                window.location.reload();
            }, 900);
        })
        .catch(function(error) {
            setActionStatus(status, error.message || 'Не удалось выполнить действие.', true);
            setButtonsDisabled(panel, false);
        });
}

function getActionEndpoints(button) {
    // Для полного анализа endpoints идут цепочкой: знания -> классификация -> отчет.
    if (button.dataset.endpoints) {
        return button.dataset.endpoints.split('|').filter(Boolean);
    }

    if (button.dataset.endpoint) {
        return [button.dataset.endpoint];
    }

    return [];
}

function runEndpointSequence(endpoints) {
    var results = [];

    return endpoints.reduce(function(sequence, endpoint) {
        return sequence.then(function() {
            return fetch(endpoint, { method: 'POST' })
                .then(function(response) {
                    if (!response.ok) {
                        return response.text().then(function(text) {
                            throw new Error(text || 'API вернул ошибку ' + response.status);
                        });
                    }
                    return response.json();
                })
                .then(function(data) {
                    results.push(data);
                    return results;
                });
        });
    }, Promise.resolve());
}

function buildSuccessMessage(results) {
    var lastResult = results[results.length - 1];

    // Коротко показываем результат последнего шага, а подробности уже видны после обновления dashboard.
    if (Array.isArray(lastResult)) {
        return 'Готово. Обработано записей: ' + lastResult.length + '. Обновляю страницу...';
    }

    if (lastResult && lastResult.id) {
        return 'Готово. Отчет создан. Обновляю страницу...';
    }

    return 'Готово. Обновляю страницу...';
}

function setActionStatus(status, message, isError) {
    if (!status) return;

    status.textContent = message;
    status.classList.toggle('is-error', Boolean(isError));
}

function setButtonsDisabled(panel, disabled) {
    if (!panel) return;

    var buttons = panel.querySelectorAll('[data-admin-action]');
    buttons.forEach(function(button) {
        button.disabled = disabled;
    });
}
