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
        self.mysql_host = os.getenv("MYSQL_HOST") or conf.get('mysql', 'host')
        self.mysql_db = os.getenv("MYSQL_DB") or conf.get('mysql', 'db')
        self.mysql_username = os.getenv("MYSQL_USERNAME") or conf.get('mysql', 'username')
        self.mysql_password = os.getenv("MYSQL_PASSWORD") or conf.get('mysql', 'password')
        logger.info("mysql_host: %s", self.mysql_host)
        logger.info("mysql_db: %s", self.mysql_db)

        self.__initConnection()
        logger.info("Successfully connected to mysql server %s", self.mysql_host)

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
            logger.error("Init error %d: %s", e.args[0], e.args[1])

    def __execute(self, query, parameters=[]):
        if isinstance(query, (list, tuple)):
            query = ' '.join(query)

        try:
            if (self.connection == None):
                self.__initConnection()
            cursor = self.connection.cursor()
            cursor.execute(query, parameters)
            return cursor
        except mysql.connector.errors.OperationalError:
            # re-initialize the connection and try again
            self.__initConnection()
            return self.__execute(query, parameters)
        except Error as e:
            logger.error("MySQL Execution error {}".format(e))
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
            if cursor is not None:
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
            try:
                cursor.fetchall() # discard remaining rows
            except:
                pass  # ignore this - there are no additional rows
            cursor.close()
   
    def dispose(self):
        if self.connection:
            self.connection.close()

    @property
    def version(self):
        return self.fetchone("SELECT VERSION()")[0]