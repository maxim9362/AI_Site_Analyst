document.addEventListener('DOMContentLoaded', function() {
    initCodeCopy();
    initAdminActions();
    initPerformanceChart();
});

function initCodeCopy() {
    // Копируем embed-код tracker.js из карточки подключения сайта.
    var codeBlocks = document.querySelectorAll('.code-block');
    codeBlocks.forEach(function(block) {
        block.style.cursor = 'pointer';
        block.title = 'Нажмите, чтобы скопировать';
        block.addEventListener('click', function() {
            var code = block.querySelector('code');
            if (!code) return;

            navigator.clipboard.writeText(code.textContent).then(function() {
                var originalText = code.textContent;
                code.textContent = 'Скопировано!';
                setTimeout(function() {
                    code.textContent = originalText;
                }, 1500);
            });
        });
    });
}

function initAdminActions() {
    // Ручные MVP-действия вызывают backend endpoints из data-атрибутов кнопок.
    var actionButtons = document.querySelectorAll('[data-admin-action]');
    actionButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            runAdminAction(button);
        });
    });
}

function initPerformanceChart() {
    var canvas = document.getElementById('performanceChart');
    var emptyEl = document.getElementById('chartEmpty');
    if (!canvas || !canvas.dataset.chart) return;

    var chartData;
    try {
        chartData = JSON.parse(canvas.dataset.chart);
    } catch (error) {
        return;
    }

    var allToggles = document.querySelectorAll('[data-chart-toggles] input[type="checkbox"]');
    var enabledToggles = document.querySelectorAll('[data-chart-toggles] input[type="checkbox"]:not([disabled])');

    enabledToggles.forEach(function(toggle) {
        toggle.addEventListener('change', function() {
            renderChart(canvas, emptyEl, chartData, getEnabledSeries(allToggles));
        });
    });

    renderChart(canvas, emptyEl, chartData, getEnabledSeries(allToggles));
    window.addEventListener('resize', function() {
        renderChart(canvas, emptyEl, chartData, getEnabledSeries(allToggles));
    });
}

function renderChart(canvas, emptyEl, chartData, enabledSeries) {
    var hasData = hasAnyData(chartData);
    if (!hasData) {
        canvas.style.display = 'none';
        if (emptyEl) emptyEl.style.display = '';
        return;
    }
    canvas.style.display = '';
    if (emptyEl) emptyEl.style.display = 'none';
    drawPerformanceChart(canvas, chartData, enabledSeries);
}

function hasAnyData(chartData) {
    var labels = chartData.labels || [];
    if (!labels.length) return false;
    var series = chartData.series || [];
    for (var i = 0; i < series.length; i++) {
        if (series[i].disabled) continue;
        var values = series[i].values || [];
        for (var j = 0; j < values.length; j++) {
            var v = values[j];
            if (typeof v === 'number' && !Number.isNaN(v) && v !== null && v !== undefined && v !== 0) {
                return true;
            }
        }
    }
    return false;
}

function getEnabledSeries(toggles) {
    var enabled = {};
    toggles.forEach(function(toggle) {
        enabled[toggle.value] = toggle.checked;
    });
    return enabled;
}

function drawPerformanceChart(canvas, chartData, enabledSeries) {
    var ratio = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    var width = Math.max(320, rect.width);
    var height = Math.max(240, rect.height || 320);
    canvas.width = width * ratio;
    canvas.height = height * ratio;

    var ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    var padding = { top: 24, right: 24, bottom: 42, left: 52 };
    var plotWidth = width - padding.left - padding.right;
    var plotHeight = height - padding.top - padding.bottom;
    var activeSeries = getDrawableSeries(chartData.series || [], enabledSeries);

    drawChartFrame(ctx, width, height, padding, plotWidth, plotHeight, chartData.labels || []);

    if (!activeSeries.length) {
        drawEmptyChartMessage(ctx, width, height, 'Выберите хотя бы одну метрику');
        return;
    }

    activeSeries.forEach(function(series) {
        drawSeriesLine(ctx, series, chartData.labels || [], padding, plotWidth, plotHeight);
    });

    drawLegend(ctx, activeSeries, padding.left, 20);
}

function getDrawableSeries(seriesList, enabledSeries) {
    return seriesList.filter(function(series) {
        if (series.disabled) return false;
        if (!enabledSeries[series.key]) return false;
        var values = series.values || [];
        if (!values.length) return false;
        return values.some(function(value) {
            return typeof value === 'number' && !Number.isNaN(value) && value !== null && value !== undefined;
        });
    });
}

function drawChartFrame(ctx, width, height, padding, plotWidth, plotHeight, labels) {
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;

    for (var i = 0; i <= 4; i += 1) {
        var y = padding.top + (plotHeight / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(padding.left + plotWidth, y);
        ctx.stroke();
    }

    ctx.fillStyle = '#6b7280';
    ctx.font = '12px Arial, sans-serif';
    ctx.textAlign = 'center';
    var visibleLabels = pickAxisLabels(labels);
    visibleLabels.forEach(function(item) {
        var x = pointX(item.index, labels.length, padding.left, plotWidth);
        ctx.fillText(formatDateLabel(item.label), x, height - 16);
    });
}

function pickAxisLabels(labels) {
    if (!labels.length) return [];
    var step = Math.max(1, Math.ceil(labels.length / 6));
    return labels
        .map(function(label, index) { return { label: label, index: index }; })
        .filter(function(item) { return item.index % step === 0 || item.index === labels.length - 1; });
}

function drawSeriesLine(ctx, series, labels, padding, plotWidth, plotHeight) {
    var values = series.values || [];
    var numericValues = values.filter(function(value) {
        return typeof value === 'number' && !Number.isNaN(value) && value !== null && value !== undefined;
    });
    if (!numericValues.length) return;

    var maxValue = Math.max.apply(null, numericValues.concat([1]));
    var minValue = Math.min.apply(null, numericValues.concat([0]));
    var range = maxValue - minValue || 1;

    ctx.strokeStyle = series.color || '#2563eb';
    ctx.fillStyle = series.color || '#2563eb';
    ctx.lineWidth = 2;
    ctx.beginPath();

    var hasStarted = false;
    values.forEach(function(value, index) {
        if (typeof value !== 'number' || Number.isNaN(value) || value === null || value === undefined) {
            hasStarted = false;
            return;
        }

        var x = pointX(index, labels.length, padding.left, plotWidth);
        var y = padding.top + plotHeight - ((value - minValue) / range) * plotHeight;

        if (!hasStarted) {
            ctx.moveTo(x, y);
            hasStarted = true;
        } else {
            ctx.lineTo(x, y);
        }
    });
    ctx.stroke();

    values.forEach(function(value, index) {
        if (typeof value !== 'number' || Number.isNaN(value) || value === null || value === undefined) return;
        var x = pointX(index, labels.length, padding.left, plotWidth);
        var y = padding.top + plotHeight - ((value - minValue) / range) * plotHeight;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
    });
}

function pointX(index, count, left, plotWidth) {
    if (count <= 1) return left + plotWidth / 2;
    return left + (plotWidth / (count - 1)) * index;
}

function drawLegend(ctx, seriesList, x, y) {
    ctx.font = '12px Arial, sans-serif';
    ctx.textAlign = 'left';
    var offsetX = 0;
    seriesList.forEach(function(series) {
        ctx.fillStyle = series.color || '#2563eb';
        ctx.fillRect(x + offsetX, y - 9, 10, 10);
        ctx.fillStyle = '#374151';
        ctx.fillText(series.label, x + offsetX + 15, y);
        offsetX += ctx.measureText(series.label).width + 42;
    });
}

function drawEmptyChartMessage(ctx, width, height, message) {
    ctx.fillStyle = '#6b7280';
    ctx.font = '14px Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(message, width / 2, height / 2);
}

function formatDateLabel(value) {
    // Hourly labels like "14:00" — return as is.
    if (/^\d{2}:\d{2}$/.test(value)) return value;
    // Daily labels like "2026-07-01" — format as DD.MM.
    var parts = String(value).split('-');
    if (parts.length === 3) return parts[2] + '.' + parts[1];
    return value;
}

function runAdminAction(button) {
    var panel = button.closest('.action-panel');
    var status = panel ? panel.querySelector('.admin-action-status') : null;
    var endpoints = getActionEndpoints(button);

    if (!endpoints.length) {
        setActionStatus(status, 'Не найден API endpoint для действия.', true);
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

    if (lastResult && lastResult.status === 'queued') {
        return 'Задача запущена в фоне. Обновляю страницу...';
    }

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
