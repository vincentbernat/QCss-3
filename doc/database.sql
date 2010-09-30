-- Database schema for QCss. PostgreSQL.

-- This schema still needs some work to create appropriate indexes.

-- We use ON DELETE CASCADE to be able to simply delete something
-- without cleaning the other tables. We also heavily rely on ON
-- UPDATE CASCADE for the same reason (i.e updating deleted
-- timestamp). We also rely on the fact that tables are updated into a
-- transaction and therefore now() keeps the same value during all the
-- transaction.

-- Rules are used to intercept INSERT operations on the table to take
-- care of updating the time travel machine. For INSERT, we will
-- search for a row with the same values and with deleted=now() and
-- update it with deleted='infinity'. Otherwise, we will try to insert
-- the new row (with created=now() and deleted='infinity'). For
-- DELETE, we will update corresponding rows with deleted=now()
-- instead when deleted='infinity'. However, this will be done
-- directly in the application since it is believed to be more
-- efficient.
--
-- For tables having an updated column, INSERT will search for
-- deleted='infinity' and update updated=now(), DELETE will update
-- like above.
--
-- For all this to work, we absolutely need that DELETE followed by
-- INSERT be in the same transaction so that the two values of now()
-- match.
--
-- Integrity is quite complex. Foreign keys should include `delete'
-- column. However, this is not as easy as this. For example, as a
-- loadbalancer may still exist from t to infinity, a virtualserver
-- could exist from t to t+1 but not from t+1 to infinity. There will
-- be no column with t+1 for the given equipment. The `delete' column
-- in a table should be between `created' and `deleted' (both
-- included) of reference. We don't check all this. However, we
-- provide triggers to update if possible the value of `deleted' if
-- the reference is updated. For example, if an equipment is deleted,
-- its `deleted' column is set to CURRENT_TIMESTAMP and the trigger
-- will update all `deleted' column accordingly.

-- This means that to delete something, we must in fact UPDATE its
-- `deleted' timestamp. Before updating something, we must delete it
-- (this means UPDATE) then INSERT it. Evrything else should be done
-- automatically, thanks to triggers.

-- Each table have a _past counterpart that has the same schema but
-- where deleted != 'infinity'. Each table has also a view _full which
-- is the join of the table and the past table. To maintain PostgreSQL
-- 8.1 compatibility, we need to copy indexes by hand (instead of
-- using INCLUDING INDEXES). We don't include DEFAULTS because there
-- is not direct insertion into past tables.

-- The configuration of PostgreSQL should use UTF-8 messages. For example:
-- lc_messages = 'en_US.UTF-8'
-- lc_monetary = 'en_US.UTF-8'
-- lc_numeric = 'en_US.UTF-8'
-- lc_time = 'en_US.UTF-8'

-- !!!!
-- When modifying this file, an upgrade procedure should be done in
-- qcss3/core/database.py.

DROP RULE IF EXISTS update_loadbalancer ON loadbalancer;
DROP RULE IF EXISTS update_virtualserver ON virtualserver;
DROP RULE IF EXISTS update_realserver ON realserver;
DROP RULE IF EXISTS insert_loadbalancer ON loadbalancer;
DROP RULE IF EXISTS insert_virtualserver ON virtualserver;
DROP RULE IF EXISTS insert_virtualserver_extra ON virtualserver_extra;
DROP RULE IF EXISTS insert_realserver ON realserver;
DROP RULE IF EXISTS insert_realserver_extra ON realserver_extra;
DROP TABLE IF EXISTS loadbalancer CASCADE;
DROP TABLE IF EXISTS loadbalancer_past CASCADE;
DROP VIEW IF EXISTS loadbalancer_full CASCADE;
DROP TABLE IF EXISTS virtualserver CASCADE;
DROP TABLE IF EXISTS virtualserver_past CASCADE;
DROP VIEW IF EXISTS virtualserver_full CASCADE;
DROP TABLE IF EXISTS virtualserver_extra CASCADE;
DROP TABLE IF EXISTS virtualserver_extra_past CASCADE;
DROP VIEW IF EXISTS virtualserver_extra_full CASCADE;
DROP TABLE IF EXISTS realserver CASCADE;
DROP TABLE IF EXISTS realserver_past CASCADE;
DROP VIEW IF EXISTS realserver_full CASCADE;
DROP TABLE IF EXISTS realserver_extra CASCADE;
DROP TABLE IF EXISTS realserver_extra_past CASCADE;
DROP VIEW IF EXISTS realserver_extra_full CASCADE;
DROP TABLE IF EXISTS action CASCADE;

CREATE TABLE loadbalancer (
  name    text		   NOT NULL,
  type	  text		   NOT NULL,
  description text	   DEFAULT '',
  created abstime	   DEFAULT CURRENT_TIMESTAMP,
  updated abstime	   DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	   DEFAULT 'infinity',
  PRIMARY KEY (name, deleted)
);
CREATE RULE insert_loadbalancer AS ON INSERT TO loadbalancer
WHERE EXISTS (SELECT 1 FROM loadbalancer
      	      WHERE name=new.name AND type=new.type
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE loadbalancer SET deleted='infinity', updated=CURRENT_TIMESTAMP::abstime
   	   WHERE name=new.name AND type=new.type
	   AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE loadbalancer_past (LIKE loadbalancer);
ALTER TABLE loadbalancer_past ADD PRIMARY KEY (name, deleted);
CREATE INDEX loadbalancer_past_deleted ON loadbalancer_past (deleted);
CREATE VIEW loadbalancer_full AS (SELECT * FROM loadbalancer UNION SELECT * FROM loadbalancer_past);

CREATE TABLE virtualserver (
  lb          text	   NOT NULL,
  vs	      text	   NOT NULL,
  name	      text	   NOT NULL,
  vip	      text	   NOT NULL,
  protocol    text	   NOT NULL,
  mode	      text	   NOT NULL,
  created     abstime	   DEFAULT CURRENT_TIMESTAMP,
  updated     abstime	   DEFAULT CURRENT_TIMESTAMP,
  deleted     abstime	   DEFAULT 'infinity',
  PRIMARY KEY (lb, vs, deleted)
);
CREATE RULE insert_virtualserver AS ON INSERT TO virtualserver
WHERE EXISTS (SELECT 1 FROM virtualserver
      	      WHERE lb=new.lb AND vs=new.vs AND name=new.name AND vip=new.vip
	      AND protocol=new.protocol
	      AND mode=new.mode AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE virtualserver SET deleted='infinity', updated=CURRENT_TIMESTAMP::abstime
      	      WHERE lb=new.lb AND vs=new.vs AND name=new.name AND vip=new.vip
	      AND protocol=new.protocol
	      AND mode=new.mode AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE virtualserver_past (LIKE virtualserver);
ALTER TABLE virtualserver_past ADD PRIMARY KEY (lb, vs, deleted);
CREATE INDEX virtualserver_past_deleted ON virtualserver_past (deleted);
CREATE VIEW virtualserver_full AS (SELECT * FROM virtualserver UNION SELECT * FROM virtualserver_past);

CREATE TABLE virtualserver_extra (
  lb          text	   NOT NULL,
  vs	      text	   NOT NULL,
  key	      text	   NOT NULL,
  value	      text	   NOT NULL,
  created     abstime	   DEFAULT CURRENT_TIMESTAMP,
  deleted     abstime	   DEFAULT 'infinity',
  PRIMARY KEY (lb, vs, key, deleted)
);
CREATE RULE insert_virtualserver_extra AS ON INSERT TO virtualserver_extra
WHERE EXISTS (SELECT 1 FROM virtualserver_extra
      	      WHERE lb=new.lb AND vs=new.vs AND key=new.key
	      AND value=new.value AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE virtualserver_extra SET deleted='infinity'
      	      WHERE lb=new.lb AND vs=new.vs AND key=new.key
	      AND value=new.value AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE virtualserver_extra_past (LIKE virtualserver_extra);
ALTER TABLE virtualserver_extra_past ADD PRIMARY KEY (lb, vs, key, deleted);
CREATE INDEX virtualserver_extra_past_deleted ON virtualserver_extra_past (deleted);
CREATE VIEW virtualserver_extra_full AS (SELECT * FROM virtualserver_extra UNION SELECT * FROM virtualserver_extra_past);

CREATE TABLE realserver (
  lb          text	   NOT NULL,
  vs	      text	   NOT NULL,
  rs	      text	   NOT NULL,
  name	      text	   NOT NULL,
  rip	      inet	   NOT NULL,
  port	      int	   NULL,
  protocol    text	   NULL,
  weight      int	   NULL,
  rstate      text  	   NOT NULL,
  sorry	      boolean	   NOT NULL DEFAULT 'f',
  created     abstime	   DEFAULT CURRENT_TIMESTAMP,
  updated     abstime	   DEFAULT CURRENT_TIMESTAMP,
  deleted     abstime	   DEFAULT 'infinity',
  PRIMARY KEY (lb, vs, rs, deleted),
  CONSTRAINT rstate_check CHECK (rstate = 'up' OR rstate = 'disabled' OR rstate = 'down' OR rstate = 'unknown')
);
CREATE INDEX realserver_sorry ON realserver (lb, vs, rs, sorry, deleted);
CREATE RULE insert_realserver AS ON INSERT TO realserver
WHERE EXISTS (SELECT 1 FROM realserver
      	      WHERE lb=new.lb AND vs=new.vs AND rs=new.rs
	      AND name=new.name AND rip=new.rip
	      AND port=new.port AND protocol=new.protocol
	      AND (weight IS NULL AND new.weight IS NULL OR weight=new.weight)
	      AND rstate=new.rstate AND sorry=new.sorry
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE realserver SET deleted='infinity', updated=CURRENT_TIMESTAMP::abstime
      	      WHERE lb=new.lb AND vs=new.vs AND rs=new.rs
	      AND name=new.name AND rip=new.rip
	      AND port=new.port AND protocol=new.protocol
	      AND (weight IS NULL AND new.weight IS NULL OR weight=new.weight)
	      AND rstate=new.rstate AND sorry=new.sorry
	      AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE realserver_past (LIKE realserver);
ALTER TABLE realserver_past ADD PRIMARY KEY (lb, vs, rs, deleted);
CREATE INDEX realserver_past_deleted ON realserver_past (deleted);
CREATE VIEW realserver_full AS (SELECT * FROM realserver UNION SELECT * FROM realserver_past);

CREATE TABLE realserver_extra (
  lb          text	   NOT NULL,
  vs	      text	   NOT NULL,
  rs	      text	   NOT NULL,
  key	      text	   NOT NULL,
  value	      text	   NOT NULL,
  created     abstime	   DEFAULT CURRENT_TIMESTAMP,
  deleted     abstime	   DEFAULT 'infinity',
  PRIMARY KEY (lb, vs, rs, key, deleted)
);
CREATE RULE insert_realserver_extra AS ON INSERT TO realserver_extra
WHERE EXISTS (SELECT 1 FROM realserver_extra
      	      WHERE lb=new.lb AND vs=new.vs AND rs=new.rs AND key=new.key
	      AND value=new.value AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE realserver_extra SET deleted='infinity'
      	      WHERE lb=new.lb AND vs=new.vs AND rs=new.rs AND key=new.key
	      AND value=new.value AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE realserver_extra_past (LIKE realserver_extra);
ALTER TABLE realserver_extra_past ADD PRIMARY KEY (lb, vs, rs, key, deleted);
CREATE INDEX realserver_extra_past_deleted ON realserver_extra_past (deleted);
CREATE VIEW realserver_extra_full AS (SELECT * FROM realserver_extra UNION SELECT * FROM realserver_extra_past);

-- This table is not indexed by time. We could use foreign keys but
-- with little added value. We prefer to not use it for consistency.
CREATE TABLE action (
  lb          text      NOT NULL,
  vs          text      NULL,
  rs          text      NULL,
  action      text      NOT NULL,
  label       text      NOT NULL,
  PRIMARY KEY (lb, vs, rs, action)
);
CREATE INDEX action_lb_vs_rs ON action (lb, vs, rs);

-- Special rules to propagate updates. These rules should work when
-- port or equipment `deleted' column is set from infinity to
-- CURRENT_TIMESTAMP.
CREATE RULE update_loadbalancer AS ON UPDATE TO loadbalancer
WHERE old.deleted='infinity' AND new.deleted=CURRENT_TIMESTAMP::abstime
DO ALSO UPDATE virtualserver SET deleted=CURRENT_TIMESTAMP::abstime
   	WHERE lb=new.name AND deleted='infinity';
CREATE RULE update_virtualserver AS ON UPDATE TO virtualserver
WHERE old.deleted='infinity' AND new.deleted=CURRENT_TIMESTAMP::abstime
DO ALSO
(UPDATE virtualserver_extra SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE lb=new.lb AND vs=new.vs AND deleted='infinity';
 UPDATE realserver SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE lb=new.lb AND vs=new.vs AND deleted='infinity');
CREATE RULE update_realserver AS ON UPDATE TO realserver
WHERE old.deleted='infinity' AND new.deleted=CURRENT_TIMESTAMP::abstime
DO ALSO UPDATE realserver_extra SET deleted=CURRENT_TIMESTAMP::abstime
   	WHERE lb=new.lb AND vs=new.vs AND rs=new.rs AND deleted='infinity';
