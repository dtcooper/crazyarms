$(function() {
    var template =  Handlebars.compile($('#liquidsoap-status-template').html())
    var $status = $('#liquidsoap-status')

    function updateTemplate(data) {
        $status.html(template(JSON.parse(data)))
    }
    updateTemplate($('#liquidsoap-status-json').text())

    var eventSource = new EventSource('sse')
    eventSource.onmessage = function(e) {
        updateTemplate(e.data)
    }
})
