FROM library/golang:buster

RUN apt-get update \
    && apt-get install -y --no-install-recommends netcat \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p $GOPATH/src/gossed

WORKDIR $GOPATH/src/gossed

RUN go get github.com/alexandrevicenzi/go-sse \
    && wget -q https://raw.githubusercontent.com/mattdanielbrown/gossed/master/gossed.go \
    && go install

CMD ["sh", "-c", "while true; do nc -lp 3001; done | gossed"]
