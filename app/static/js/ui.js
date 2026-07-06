document.addEventListener('DOMContentLoaded', function() {
    initInfoPopovers();
});

function initInfoPopovers() {
    var popovers = Array.prototype.slice.call(document.querySelectorAll('details.info-popover'));
    if (!popovers.length) return;

    function isTouchMode() {
        return window.matchMedia && window.matchMedia('(hover: none), (pointer: coarse)').matches;
    }

    function closeOthers(current) {
        popovers.forEach(function(popover) {
            if (popover !== current) popover.open = false;
        });
    }

    popovers.forEach(function(popover) {
        var summary = popover.querySelector('summary');
        if (!summary) return;

        popover.addEventListener('mouseenter', function() {
            if (isTouchMode()) return;
            closeOthers(popover);
            popover.open = true;
        });

        popover.addEventListener('mouseleave', function() {
            if (isTouchMode()) return;
            popover.open = false;
        });

        summary.addEventListener('click', function(event) {
            if (isTouchMode()) return;
            event.preventDefault();
            closeOthers(popover);
            popover.open = true;
        });

        popover.addEventListener('focusout', function(event) {
            if (isTouchMode()) return;
            if (!popover.contains(event.relatedTarget)) {
                popover.open = false;
            }
        });
    });

    document.addEventListener('mousemove', function(event) {
        if (isTouchMode()) return;
        popovers.forEach(function(popover) {
            if (!popover.open) return;
            if (!popover.contains(event.target)) {
                popover.open = false;
            }
        });
    });

    document.addEventListener('touchstart', function(event) {
        var activePopover = event.target.closest && event.target.closest('details.info-popover');
        popovers.forEach(function(popover) {
            if (popover !== activePopover) popover.open = false;
        });
    }, { passive: true });
}
