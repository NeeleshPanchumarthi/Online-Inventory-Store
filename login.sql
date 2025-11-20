--create the table for the user with primary keys in oracle sql 
CREATE TABLE users (
    full_name VARCHAR2(255) NOT NULL,
    email VARCHAR2(255) NOT NULL,
    password VARCHAR2(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (email)
);

--create a procedure to insert a user into the users table
CREATE OR REPLACE PROCEDURE insert_user(
    p_full_name IN VARCHAR2,
    p_email IN VARCHAR2,
    p_password IN VARCHAR2
)
AS
BEGIN
    INSERT INTO users (full_name, email, password)
    VALUES (p_full_name, p_email, p_password);
    COMMIT;
EXCEPTION
    WHEN DUP_VAL_ON_INDEX THEN
        RAISE_APPLICATION_ERROR(-20001, 'Email already exists');
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END insert_user;
/

--create a function to check if a user exists in the users table by checking the email and password
CREATE OR REPLACE FUNCTION check_user(
    p_email IN VARCHAR2,
    p_password IN VARCHAR2
) RETURN BOOLEAN
IS
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM users
    WHERE email = p_email
    AND password = p_password;
    
    RETURN v_count > 0;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END check_user;
/
COLUMN full_name FORMAT A20
COLUMN email FORMAT A30
COLUMN password FORMAT A60 WORD_WRAPPED
COLUMN created_at FORMAT A20

-- Clear any previous line size settings
SET LINESIZE 200
SET PAGESIZE 50



