(function($) {
    function selectAssetSource() {
        var on = $('#id_source').val()
        if (on) {
            var off = (on == 'file') ? 'url' : 'file'
            $('div.form-row.field-' + on).show()
            $('#id_' + off).val('')
            $('div.form-row.field-' + off).hide()
        }
    }

    $(function() {
        // Detect add page (has a #source_id input)
        if ($('#id_source').length) {
            selectAssetSource()
            $('#id_source').change(selectAssetSource)
        }
    })
})(window.jQuery)
