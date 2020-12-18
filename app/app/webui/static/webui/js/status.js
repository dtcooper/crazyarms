// Based off https://stackoverflow.com/a/34252942
Handlebars.registerHelper('ifEqual', function(arg1, arg2, options) {
    return (arg1 == arg2) ? options.fn(this) : options.inverse(this)
});
Handlebars.registerHelper('ifNotEqual', function(arg1, arg2, options) {
    return (arg1 != arg2) ? options.fn(this) : options.inverse(this)
});
Handlebars.registerHelper('ifContains', function(arg1, arg2, options) {
    return (Array.isArray(arg1) && arg1.includes(arg2)) ? options.fn(this) : options.inverse(this)
});

function prettyInterval(seconds) {
    var hours = Math.floor(seconds / 60 / 60)
    var minutes = Math.floor((seconds / 60) % 60)
    var seconds = Math.round(seconds % 60).toString().padStart(2, '0')
    if (hours > 0) {
        return hours + ':' + minutes.toString().padStart(2, '0') + ':' + seconds
    } else {
        return minutes + ':' + seconds
    }
}

function updateTimers() {
    $('body .track-end').each(function(i, elem) {
        var endTime = new Date($(elem).data('end') * 1000)
        var secondsLeft = Math.max((endTime.getTime() - new Date()) / 1000, 0)
        $(elem).text(prettyInterval(secondsLeft))
    });
    $('body .since-timer').each(function(i, elem) {
        var startTime = new Date($(elem).data('since') * 1000)
        var seconds = Math.max((new Date() - startTime.getTime()) / 1000, 0)
        $(elem).text(prettyInterval(seconds))
    });
}

$(function() {
    var harborStatusTemplate =  Handlebars.compile($('#harbor-status-template').html())
    var $status = $('#harbor-status')

    function updateHarborStatusTemplate(data) {
        data = JSON.parse(data)
        if (data && data.harbor) {
            var context = $.extend(data.harbor, perms)
            $status.html(harborStatusTemplate(context))
        } else {
            $status.html('<p class="error">The harbor appears to be down. Please check the server logs or again later.</p>')
        }
        updateTimers()
    }
    updateHarborStatusTemplate($('#harbor-status-json').text())

    var eventSource = new EventSource('/sse')
    eventSource.onmessage = function(e) {
        updateHarborStatusTemplate(e.data)
    }

    setInterval(updateTimers, 1000)

    if (perms.showAutoDJRequests) {
        setTimeout(function() {
            // Needs to initialize slightly delayed for some reason?
            $('.django-select2').djangoSelect2({placeholder: 'Search for a track', dropdownAutoWidth: true})
        }, 500)
        if (perms.canMakeAutoDJRequests) {
            $('#autodj-request-form').submit(function(e) {
                e.preventDefault()
                var $asset = $('#id_asset')

                if ($asset.val()) {
                    var postData = $(this).serialize()
                    $asset.val(null).trigger('change') //clear select2
                    $.post(autoDJRequestsUrl, postData, function(response) {
                        addMessage('info', response)
                    }).fail(function() {
                        addMessage('error', 'An error occurred while making your AutoDJ request.')
                    })
                }
            });
        }
    }

    $('body').on('click', '.skip-btn', function(e) {
        e.preventDefault()
        var sourceId = $(this).data('id')
        var sourceName = $(this).data('name')
        if (confirm('Are you skip you want to skip the current ' + sourceName + ' track?')) {
            var postData = {"csrfmiddlewaretoken": csrfToken, "name": sourceName, "id": sourceId}
            $.post(statusSkipUrl, postData, function(response) {
                addMessage('info', response)
            }).fail(function() {
                addMessage('error', 'An error occurred while skipping ' + sourceName)
            })
        }
    });

    $('body').on('click', '.boot-btn', function(e) {
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
                addMessage('info', response)
            }).fail(function() {
                addMessage('error', 'An error occurred while banning ' + user)
            })
        }
    })
})
