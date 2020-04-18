# -*- encoding: utf-8 -*-

import mysql.connector
from mysql.connector import Error
import logging
import operator
import os.path

from collections import defaultdict

logger = logging.getLogger("isso")

from isso.compat import buffer

from isso.mysql.comments import Comments
from isso.mysql.threads import Threads
from isso.mysql.spam import Guard
from isso.mysql.preferences import Preferences


class MySQL:
    """DB-dependend wrapper around MySQL.

    Register a trigger for automated orphan removal.
    """


    def __init__(self, conf):
        self.conf = conf
        self.mysql_host = conf.get('mysql', 'host')
        self.mysql_db = conf.get('mysql', 'db')
        self.mysql_username = conf.get('mysql', 'username')
        self.mysql_password = conf.get('mysql', 'password')
        print("mysql_host: %s" % self.mysql_host)
        print("mysql_db: %s" % self.mysql_db)
        print("mysql_username: %s" % self.mysql_username)
        print("mysql_password: %s" % self.mysql_password)

        self.__initConnection()
        print("Successfully connected to mysql server %s" % self.mysql_host)

        self.preferences = Preferences(self)
        self.threads = Threads(self)
        self.comments = Comments(self)
        self.guard = Guard(self)

    def __initConnection(self):
        try:
            self.connection = mysql.connector.connect(host=self.mysql_host,
                                                      database=self.mysql_db,
                                                      user=self.mysql_username,
                                                      password=self.mysql_password,
                                                      use_pure=True) # necessary for voters pickling
        except Error as e:
            print("Init error %d: %s" % (e.args[0], e.args[1]))

    def __execute(self, query, parameters=[]):
        if isinstance(query, (list, tuple)):
            query = ' '.join(query)

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, parameters)
            return cursor
        except mysql.connector.errors.OperationalError:
            # re-initialize the connection and try again
            self.__initConnection()
            return self.__execute(query, parameters)
        except Error as e:
            print("MySQL Execution error {}".format(e))
            raise

    def __select(self, query, parameters):
        return self.__execute(query, parameters)
   
    def commit(self, query, parameters=[]):
        cursor = self.__execute(query, parameters)
        try:
            self.connection.commit()
            rc = cursor.rowcount
            cursor.close()
            return rc
        finally:
            cursor.close()

    def execute(self, query, parameters=[]):
        try:
            cursor = self.__execute(query, parameters)
        finally:
            cursor.close()
 
    def fetchall(self, query, parameters=[]):
        cursor = self.__select(query, parameters)
        try:
            res = cursor.fetchall()
            return res
        finally:
            cursor.close()
   
    def fetchone(self, query, parameters=[]):
        cursor = self.__select(query, parameters)
        try:
            res = cursor.fetchone()
            return res
        finally:
            cursor.close()
   
    def dispose(self):
        if self.connection:
            self.connection.close()

    @property
    def version(self):
        return self.fetchone("SELECT VERSION()")[0]