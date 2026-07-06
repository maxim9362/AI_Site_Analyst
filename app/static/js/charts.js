document.addEventListener('DOMContentLoaded', function() {
    restoreGscScrollPosition();
    initMetricCharts();
    initGscPeriodNavigation();
});

function initMetricCharts(root) {
    root = root || document;
    var canvases = root.querySelectorAll('canvas[data-chart]');
    canvases.forEach(function(canvas) {
        if (canvas.dataset.chartInitialized === 'true') return;
        canvas.dataset.chartInitialized = 'true';
        var emptyEl = document.getElementById(canvas.id + 'Empty');
        var chartData;
        try {
            chartData = JSON.parse(canvas.dataset.chart);
        } catch (error) {
            return;
        }

        var container = canvas.closest('.performance-card') || document;
        var allToggles = container.querySelectorAll('[data-chart-toggles] input[type="checkbox"]');
        var enabledToggles = container.querySelectorAll('[data-chart-toggles] input[type="checkbox"]:not([disabled])');

        enabledToggles.forEach(function(toggle) {
            toggle.addEventListener('change', function() {
                renderMetricChart(canvas, emptyEl, chartData, getEnabledMetricSeries(allToggles));
            });
        });

        renderMetricChart(canvas, emptyEl, chartData, getEnabledMetricSeries(allToggles));
        window.addEventListener('resize', function() {
            renderMetricChart(canvas, emptyEl, chartData, getEnabledMetricSeries(allToggles));
        });
    });
}

function initGscPeriodNavigation(root) {
    root = root || document;
    var links = root.querySelectorAll('.gsc-period-switcher a[href]');
    links.forEach(function(link) {
        if (link.dataset.gscPeriodInitialized === 'true') return;
        link.dataset.gscPeriodInitialized = 'true';
        link.addEventListener('click', function(event) {
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            updateGscSection(link.href);
        });
    });
}

function updateGscSection(url) {
    var currentSection = document.getElementById('gsc-search-section');
    if (!currentSection) {
        navigateToGscPeriod(url);
        return;
    }

    var previousScrollY = window.scrollY;
    currentSection.classList.add('is-loading');

    if (typeof XMLHttpRequest === 'undefined' || typeof DOMParser === 'undefined') {
        navigateToGscPeriod(url);
        return;
    }

    requestGscSection(url)
        .then(function(html) {
            var parser = new DOMParser();
            var doc = parser.parseFromString(html, 'text/html');
            var nextSection = doc.getElementById('gsc-search-section');
            if (!nextSection) throw new Error('Search Console section was not found');

            currentSection.replaceWith(nextSection);
            window.history.pushState({}, '', url);

            window.scrollTo(window.scrollX, previousScrollY);
            window.requestAnimationFrame(function() {
                window.scrollTo(window.scrollX, previousScrollY);
            });
            initMetricCharts(nextSection);
            initGscPeriodNavigation(nextSection);
        })
        .catch(function() {
            navigateToGscPeriod(url);
        });
}

function navigateToGscPeriod(url) {
    try {
        sessionStorage.setItem('gscScrollY', String(window.scrollY));
    } catch (error) {
        // sessionStorage can be unavailable in some embedded browsers.
    }
    window.location.href = url.split('#')[0];
}

function restoreGscScrollPosition() {
    var savedScrollY = null;
    try {
        savedScrollY = sessionStorage.getItem('gscScrollY');
        sessionStorage.removeItem('gscScrollY');
    } catch (error) {
        savedScrollY = null;
    }
    if (savedScrollY === null) return;

    var targetY = parseInt(savedScrollY, 10);
    if (Number.isNaN(targetY)) return;

    window.scrollTo(window.scrollX, targetY);
    window.requestAnimationFrame(function() {
        window.scrollTo(window.scrollX, targetY);
    });
}

function requestGscSection(url) {
    return new Promise(function(resolve, reject) {
        var request = new XMLHttpRequest();
        request.open('GET', url, true);
        request.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        request.onload = function() {
            if (request.status >= 200 && request.status < 300) {
                resolve(request.responseText);
                return;
            }
            reject(new Error('Failed to load Search Console section'));
        };
        request.onerror = function() {
            reject(new Error('Failed to load Search Console section'));
        };
        request.send();
    });
}

function renderMetricChart(canvas, emptyEl, chartData, enabledSeries) {
    if (!hasMetricChartData(chartData)) {
        canvas.style.display = 'none';
        if (emptyEl) emptyEl.style.display = '';
        return;
    }
    canvas.style.display = '';
    if (emptyEl) emptyEl.style.display = 'none';
    drawMetricChart(canvas, chartData, enabledSeries);
}

function hasMetricChartData(chartData) {
    var labels = chartData.labels || [];
    if (!labels.length) return false;
    var series = chartData.series || [];
    for (var i = 0; i < series.length; i++) {
        if (series[i].disabled) continue;
        var values = series[i].values || [];
        for (var j = 0; j < values.length; j++) {
            var value = values[j];
            if (typeof value === 'number' && !Number.isNaN(value) && value !== 0) return true;
        }
    }
    return false;
}

function getEnabledMetricSeries(toggles) {
    var enabled = {};
    toggles.forEach(function(toggle) {
        enabled[toggle.value] = toggle.checked;
    });
    return enabled;
}

function drawMetricChart(canvas, chartData, enabledSeries) {
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
    var activeSeries = getDrawableMetricSeries(chartData.series || [], enabledSeries);

    drawMetricChartFrame(ctx, width, height, padding, plotWidth, plotHeight, chartData.labels || []);

    if (!activeSeries.length) {
        drawMetricEmptyMessage(ctx, width, height, 'Выберите хотя бы одну метрику');
        return;
    }

    activeSeries.forEach(function(series) {
        drawMetricSeriesLine(ctx, series, chartData.labels || [], padding, plotWidth, plotHeight);
    });
    drawMetricLegend(ctx, activeSeries, padding.left, 20);
}

function getDrawableMetricSeries(seriesList, enabledSeries) {
    return seriesList.filter(function(series) {
        if (series.disabled) return false;
        if (!enabledSeries[series.key]) return false;
        var values = series.values || [];
        return values.some(function(value) {
            return typeof value === 'number' && !Number.isNaN(value);
        });
    });
}

function drawMetricChartFrame(ctx, width, height, padding, plotWidth, plotHeight, labels) {
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
    pickMetricAxisLabels(labels).forEach(function(item) {
        var x = metricPointX(item.index, labels.length, padding.left, plotWidth);
        ctx.fillText(formatMetricDateLabel(item.label), x, height - 16);
    });
}

function pickMetricAxisLabels(labels) {
    if (!labels.length) return [];
    var step = Math.max(1, Math.ceil(labels.length / 6));
    return labels
        .map(function(label, index) { return { label: label, index: index }; })
        .filter(function(item) { return item.index % step === 0 || item.index === labels.length - 1; });
}

function drawMetricSeriesLine(ctx, series, labels, padding, plotWidth, plotHeight) {
    var values = series.values || [];
    var numericValues = values.filter(function(value) {
        return typeof value === 'number' && !Number.isNaN(value);
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
        if (typeof value !== 'number' || Number.isNaN(value)) {
            hasStarted = false;
            return;
        }

        var x = metricPointX(index, labels.length, padding.left, plotWidth);
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
        if (typeof value !== 'number' || Number.isNaN(value)) return;
        var x = metricPointX(index, labels.length, padding.left, plotWidth);
        var y = padding.top + plotHeight - ((value - minValue) / range) * plotHeight;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
    });
}

function metricPointX(index, count, left, plotWidth) {
    if (count <= 1) return left + plotWidth / 2;
    return left + (plotWidth / (count - 1)) * index;
}

function drawMetricLegend(ctx, seriesList, x, y) {
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

function drawMetricEmptyMessage(ctx, width, height, message) {
    ctx.fillStyle = '#6b7280';
    ctx.font = '14px Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(message, width / 2, height / 2);
}

function formatMetricDateLabel(value) {
    if (/^\d{2}:\d{2}$/.test(value)) return value;
    var parts = String(value).split('-');
    if (parts.length === 3) return parts[2] + '.' + parts[1];
    return value;
}
