{% load services %}

# Things common to harbor.liq and upstream.liq
PLAYOUT_LOG_ENTRY_TABLE_NAME = {{ playout_log_entry_table_name|liqval }}
CARB_VERSION = getenv('CARB_VERSION')

{% for var, value in event_types %}
    EVENT_{{ var }} = {{ value|liqval }}
{% endfor %}

def safe_quote(s)
    # Needed because of https://github.com/savonet/liquidsoap/issues/1215
    if string.match(pattern='[^\\w@%+=:,./-]', s) then
        "'" ^ string.replace(pattern="'", fun(_) -> "'\"'\"'", s) ^ "'"
    else
        s
    end
end

is_shutting_down = ref false
current_source_name = ref 'N/A'
def log_event(~extras=[], ~type=EVENT_GENERAL, ~async=true, description)
    if not !is_shutting_down then
        def log_event_func()
            log('Logging playout event (#{type}): #{description}')

            # Add description, active source and default event type
            values = list.append([('description', description), ('active_source', !current_source_name),
                                ('event_type', type)], extras)

            columns = string.concat(separator=', ', list.map(fst, values))
            # Quote values (wrap in single quotes and double all single quotes in value)
            values = list.map(fun(v) -> "'" ^ string.replace(pattern="'", fun(_) -> "''", snd(v)) ^ "'", values)
            values = string.concat(separator=', ', values)
            sql = 'INSERT INTO #{PLAYOUT_LOG_ENTRY_TABLE_NAME} (created, #{columns}) VALUES (NOW(), #{values});'

            cmd = 'PGPASSWORD=postgres psql -U postgres -h db -c #{safe_quote(sql)}'
            if not test_process(cmd) then
                log("ERROR: couldn't log playout event with command: #{cmd}")
            end
        end
        if async then
            add_timeout(fast=false, 0., fun() -> begin
                log_event_func()
                -1.
            end)
        else
            log_event_func()
        end
    end
end

on_shutdown(fun() -> begin
    log_event(async=false, '#{SCRIPT_NAME} is shutting down')
    is_shutting_down := true
end)

log_event(async=false, '#{SCRIPT_NAME} came online (version: #{CARB_VERSION})')
