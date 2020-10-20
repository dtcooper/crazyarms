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
        // No value for this on add page
        if ($('#id_source').val()) {
            selectAssetSource()
            $('#id_source').change(selectAssetSource)
        }
    })
})(window.jQuery)
