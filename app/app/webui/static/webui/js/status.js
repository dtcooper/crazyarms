$(function() {
    var template =  Handlebars.compile($('#liquidsoap-status-template').html())
    var $status = $('#liquidsoap-status')

    function updateTemplate(data) {
        var context = {"sources": JSON.parse(data), "showBoot": showBoot, "showBan": showBan}
        $status.html(template(context))
    }
    updateTemplate($('#liquidsoap-status-json').text())

    var eventSource = new EventSource('/sse')
    eventSource.onmessage = function(e) {
        updateTemplate(e.data)
    }

    $('body').on('click', '.boot-btn', function (e) {
        e.preventDefault()
        var shouldBoot = false
        var time = $(this).data('time'),
            user = $(this).data('name'),
            userId = $(this).data('id'),
            text = $(this).data('text')

        if (time == 'permanent') {
            var promptOut = prompt('Are you SURE you want to PERMANENTLY BAN ' + user + ' by setting their '
                + 'harbor authorization to never.\n\nPlease type "YES" to below to confirm.')
            if (promptOut) {
                shouldBoot = promptOut.toLowerCase().indexOf('yes') != -1
            }
        } else {
            shouldBoot = confirm('Are you SURE you want to ban ' + user + ' for ' + text + '?')
        }

        if (shouldBoot) {
            var postData = {"time": time, "user_id": userId, "text": text, "csrfmiddlewaretoken": csrfToken}
            $.post(statusBootUrl, postData, function(response) {
                addMessage('success', response)
            }).fail(function() {
                addMessage('error', response)
                alert('An error occurred while banning ' + user);
            })
        } else {
            alert('Operation canceled.')
        }
    })
})
