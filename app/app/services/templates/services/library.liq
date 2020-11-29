{% load services %}

# Things common to harbor.liq and upstream.liq
TABLE_NAME = {{ table_name|liqval }}

{% for var, value in event_types %}
    EVENT_{{ var }} = {{ value|liqval }}
{% endfor %}

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
            sql = 'INSERT INTO #{TABLE_NAME} (created, #{columns}) VALUES (NOW(), #{values});'

            cmd = 'PGPASSWORD=postgres psql -U postgres -h db -c "$SQL"'
            if not test_process(env=[('SQL', sql)], cmd) then
                log("ERROR: couldn't log playout event with command: #{cmd} / sql: #{sql}")
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

log_event(async=false, '#{SCRIPT_NAME} came online')
