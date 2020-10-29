(function($) {
    function hideFieldsForLocalServer() {
        var isLocalIcecast = $('#id_local_icecast').prop('checked')
        var $formFields = $('.form-row.field-' + ['hostname', 'protocol', 'port', 'username', 'password'].join(', .form-row.field-'))

        if (isLocalIcecast) {
            $formFields.hide()
        } else {
            $formFields.show()
        }
    }

    $(function() {
        // Detect add page (has a #source_id input)
        hideFieldsForLocalServer()
        $('#id_local_icecast').change(hideFieldsForLocalServer)
    })
})(window.jQuery)
