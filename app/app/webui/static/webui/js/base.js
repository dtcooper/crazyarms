function updateMessageContainer() {
    if ($('.message-list li').length > 0) {
        $('.message-container').show()
    } else {
        $('.message-container').hide()
    }
}

function addMessage(level, message) {
    var $message = $('<em>')
    $message.text(message)
    $('.message-list').append('<li class="' + level +'">' + $message.html()
        + '  <a href="#" class="close-message">[dismiss]</a></li>')
    updateMessageContainer()
}

var audio = new Audio

$(function() {
    $('body').on('click', '.close-message', function(e) {
        e.preventDefault()
        $(this).closest('li').remove()
        updateMessageContainer()
    })

    $('nav a[href="' + window.location.pathname + '"]').each(function(i, elem) {
       $(elem).addClass('current-page');
    });

    updateMessageContainer()

    var stream = new Audio
    var isPlaying = false
    var playText = $('#play-btn').text()

    $('#play-btn').click(function() {
        $(this).toggleClass(['bg-green', 'bg-red'])
        if (isPlaying) {
            stream.pause()
            stream.src = ''
            $(this).text(playText)
        } else {
            stream.src = '/live'
            stream.play()
            $(this).text('\u25A0 Stop Playing Stream')
        }
        isPlaying = !isPlaying
    })

    $('.confirm-btn').click(function(event) {
        if (!confirm($(this).data('confirm-text'))) {
            event.preventDefault()
        }
    });
})
