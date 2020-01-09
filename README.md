# Root-Me Badge Generator

## Description

**Root-Me Badge Generator** is a web application script that generates badges from Root-me profiles.

The original idea came from *Podalirius* on the Root-Me forums (https://www.root-me.org/?page=forum&id_thread=12859) \
I forked [this project](https://github.com/HexPandaa/RootMe-Badge-Generator) in order to use his static png badge generator. I changed the way to fetch data from [Root-Me website](https://www.root-me.org/) using my custom API (see [https://github.com/zteeed/Root-Me-API](https://github.com/zteeed/Root-Me-API)). \
Then, i built the web application and added a HackTheBox theme in order to add it next to my HackTheBox badge on [my website](https://duboc.xyz/about)

## Configuration

- [dev] edit `.env` file 
- [prod] edit `ENV` attributes inside the `Dockerfile`.

Example:
```
ENV API_URL https://api.www.root-me.org
ENV URL https://root-me-badge.hackademint.org
ENV STORAGE_FOLDER storage_clients
ENV ROOTME_ACCOUNT_USERNAME rootme_username
ENV ROOTME_ACCOUNT_PASSWORD password 
```

`ROOTME_ACCOUNT_USERNAME` and `ROOTME_ACCOUNT_PASSWORD` stands for the credentials for a valid RootMe account. \
`URL` is the external URI where the application can be reached.

## Install 

```
docker build -t badge_generator .
docker run -d -p 5000:80 --name badge_generator badge_generator
```

## Result

### Home page

![](./example/screenshot1.png)

## Fill the form with my RootMe username
![](./example/screenshot2.png)

# Static PNG Badges
![](./example/screenshot3.png)

# Dynamic JS Badge
![](./example/screenshot4.png)

