CREATE TABLE users (
    id INT PRIMARY KEY,
    Name NVARCHAR(255) NOT NULL,
    Industry NVARCHAR(255) NOT NULL, 
    Country NVARCHAR(255) NOT NULL,
    Internal_Audit INT NOT NULL,
    Company_Size INT NOT NULL, 
    Using_Solution CHAR NOT NULL,
);

SELECT * FROM users

ALTER TABLE users 
ADD Score INT NOT NULL;

CREATE TABLE industries(
    id INT PRIMARY KEY,
    Name NVARCHAR(255) NOT NULL UNIQUE,
);

CREATE TABLE Countries(
    id INT PRIMARY KEY,
    Name NVARCHAR(255) NOT NULL UNIQUE,
);

ALTER TABLE users
ADD country_id INT FOREIGN KEY REFERENCES Countries(id);