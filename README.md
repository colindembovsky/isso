# Isso - with MySQL
This is a fork of [Martin Zimmermann](https://github.com/posativ)'s great [Isso repo](https://github.com/posativ/isso).

All I did was add MySQL support!

> Note: I have not tested this thoroughly - just enough to get it to work reasonably for my needs. I turn voting off, so I have not fully tested voting features with MySQL.

## MySQL Config
This version of Isso assumes that a MySQL database exists, so you need to create it before starting Isso.

Simply add the following section to the `isso.cfg` file to change the data layer to use MySQL:

```
# specify this section if you want to use mysql
# you can also set these as environment variables:
# - MYSQL_HOST
# - MYSQL_DB
# - MYSQL_USERNAME
# - MYSQL_PASSWORD
# env vars take preference

[mysql]
# mysql host
host = mysql
# mysql database name
db = comments
# mysql username
username = isso
# mysql password
password = SomeL0ngP@ssw0rd
```
