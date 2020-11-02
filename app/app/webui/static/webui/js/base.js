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

$(function() {
    $('body').on('click', '.close-message', function (e) {
        e.preventDefault()
        $(this).closest('li').remove()
        updateMessageContainer()
    })

    updateMessageContainer()
})
