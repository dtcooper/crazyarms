var updateHarborStatusInterval = 15000 // in ms

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
    var upcomingStatusTemplate = Handlebars.compile($('#upcoming-status-template').html())
    var lastStatusData = null
    var $status = $('#harbor-status')
    var $upcoming = $('#upcoming-status')

    function updateHarborStatus(data) {
        data = lastStatusData = JSON.parse(data)

        if (data) {
            var context = $.extend(data, perms)
            $status.html(harborStatusTemplate(context))
        } else {
            $status.html('<p class="error">The harbor appears to be down. Please try again later.</p>')
        }
        updateTimers()
    }
    updateHarborStatus($('#harbor-status-json').text())

    var eventSource = new EventSource('/sse')
    eventSource.onmessage = function(e) {
        updateHarborStatus(e.data)
    }
    eventSource.onerror = function() {
        updateHarborStatus(null)
    }

    function updateUpcomingStatus(data) {
        if (data) {
            if (lastStatusData) {
                for (var i = 0; i < lastStatusData.sources.length; i++) {
                    var source = lastStatusData.sources[i]
                    if (source.is_current_stream && source.id == lastStatusData.source_ids.prerecord) {
                        data.unshift({date: 'now', title: (lastStatusData.metadata.title || 'unknown'), type: 'Scheduled Broadcast'})
                        data.pop()  // remove from the list, since we're adding to it
                        break
                    }
                }
            }

            $upcoming.html(upcomingStatusTemplate(data))
        } else {
            $upcoming.html('<p class="error">The was an error fetching the schedule. Please try again later.</p>')
        }
    }

    function updateUpcomingStatusTimeout() {
        $.get('?upcoming_status_ajax=1', function(data) {
            updateUpcomingStatus(data)
            setTimeout(updateUpcomingStatusTimeout, updateHarborStatusInterval)
        }).fail(function() {
            updateUpcomingStatus(null)
            setTimeout(updateUpcomingStatusTimeout, updateHarborStatusInterval * 2)
        })
    }

    updateUpcomingStatus(JSON.parse($('#upcoming-status-json').text()))
    setTimeout(updateUpcomingStatusTimeout, updateHarborStatusInterval)

    setInterval(updateTimers, 1000)


    if (perms.showAutoDJRequests) {
        setTimeout(function() {
            // Needs to initialize slightly delayed for some reason otherwise placeholder doesn't show
            $('.django-select2').djangoSelect2({placeholder: 'Search for a track to request...', dropdownAutoWidth: true})
        }, 500)
        $('.request-btn').click(function(e) {
            e.preventDefault()
            var $asset = $('#id_asset')
            var assetId = $asset.val()

            if (assetId) {
                var postData = {csrfmiddlewaretoken: csrfToken, asset: assetId}
                $asset.val(null).trigger('change') //clear select2
                $.post(autoDJRequestsUrl, postData, function(response) {
                    addMessage('warning', response)
                }).fail(function() {
                    addMessage('error', 'An error occurred while making your AutoDJ request.')
                })
            }
        })
    }

    $('body').on('click', '.skip-btn', function(e) {
        e.preventDefault()
        var sourceId = $(this).data('id')
        var sourceName = $(this).data('name')
        if (confirm('Are you skip you want to skip the current ' + sourceName + ' track?')) {
            var postData = {csrfmiddlewaretoken: csrfToken, name: sourceName, id: sourceId}
            $.post(skipUrl, postData, function(response) {
                addMessage('warning', response)
            }).fail(function() {
                addMessage('error', 'An error occurred while skipping ' + sourceName)
            })
        }
    });

    $('body').on('click', '.boot-btn', function(e) {
        e.preventDefault()
        var shouldBoot = false
        var messageType = 'warning'
        var time = $(this).data('time'),
            user = $(this).data('name'),
            userId = $(this).data('id'),
            text = $(this).data('text')

        if (time == 'permanent') {
            var promptOut = prompt('Are you SURE you want to PERMANENTLY BAN ' + user + ' by setting their '
                + 'harbor authorization to never.\n\nPlease type "YES" to below to confirm.')
            if (promptOut) {
                messageType = 'error'  // red message for ban
                shouldBoot = promptOut.toLowerCase().indexOf('yes') != -1
            }
        } else {
            shouldBoot = confirm('Are you SURE you want to ban ' + user + ' for ' + text + '?')
        }

        if (shouldBoot) {
            var postData = {csrfmiddlewaretoken: csrfToken, time: time, user_id: userId, text: text}
            $.post(bootUrl, postData, function(response) {
                addMessage(messageType, response)
            }).fail(function() {
                addMessage('error', 'An error occurred while banning ' + user)
            })
        }
    })
})
