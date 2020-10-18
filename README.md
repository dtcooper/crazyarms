# Crazy Arms Radio Backend

## TODOs

* **THIS README**
* Docs: Initial setup
    - env file
    - docker build
* Docs: Account creation
* Docs: Static deploy?
* Docs: Updating section (Similar to AzuraCast self-update)
    - docker re-build
    - migrations
* Liquidsoap interactive telnet container, similar to container logs
    - https://github.com/nirui/sshwifty
* Use this [Go supervisord implementation](https://github.com/ochinchina/supervisord)


## Quick Setup

Make sure Docker + docker-compose is installed (Docker Desktop on macOS).

To start CARB,

```
git clone git@github.com:dtcooper/carb.git
cd carb
./compose.sh up
```

Then in your browser go to http://localhost/

To stop, press `CTRL+C`

## License
 
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
