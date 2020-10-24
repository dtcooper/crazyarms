(function($) {
    function showHideGoogleCalenderGracePeriods() {
        var harborAuth = $('#id_harbor_auth').val()
        var $formRow = $('.form-row.field-google_calender_entry_grace_minutes.field-google_calender_exit_grace_minutes')
        if (harborAuth == 'g') {
            $formRow.show()
        } else {
            $formRow.hide()
        }
    }

    $(function() {
        // Detect add page (has a #source_id input)
        showHideGoogleCalenderGracePeriods()
        $('#id_harbor_auth').change(showHideGoogleCalenderGracePeriods)
    })
})(window.jQuery)
