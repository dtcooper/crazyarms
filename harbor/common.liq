def error(s)
    print(s)
    log(s)
    exit(1)
end

def conf(name, ~allow_empty=false)
    value = getenv(name)
    if not allow_empty and value == '' then
        error('Configuration value "' ^ name ^ ' not set. Consider running with '
              ^ '"./run.sh" to set environment. Shutting down.')
    end
    value
end

def conf_int(name)
    int_of_string(conf(name))
end

def conf_float(name)
    float_of_string(conf(name))
end

def conf_bool(name)
    value = string.case(string.trim(conf(allow_empty=true, name)))
    not (value == '' or value == 'false' or value == 'f' or value == '0')
end

daemonize = argv(1) != ""
script_name = if daemonize then argv(1) else 'default' end
if daemonize then
    set('log.file', true)
    set('log.file.path', '/var/log/liquidsoap/#{script_name}.log')
    set('log.file.perms', 432)
end

if file.exists('/.dockerenv') then
    # Docker only! Otherwise always localhost.
    set('server.telnet.bind_addr', '0.0.0.0')
end
