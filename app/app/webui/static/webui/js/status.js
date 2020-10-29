function refreshStatus() {
    $.get(statusURL + '?table_only=1', function(html) {
        $('#status-table').html((new Date()) + '<br>' + html)
    })
}

$(function() {
    setInterval(refreshStatus, 2500)
});
