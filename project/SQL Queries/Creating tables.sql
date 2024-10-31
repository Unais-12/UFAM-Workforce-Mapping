DROP TABLE Users
DROP TABLE UserScores

CREATE TABLE UserScores (
    id INT PRIMARY KEY IDENTITY(1,1),
    user_id INT,
    category NVARCHAR(255),
    Score INT,
    FOREIGN KEY(user_id) REFERENCES Users(Id)   
);

CREATE TABLE Users(
    Id INT PRIMARY KEY IDENTITY(1,1),
    Name NVARCHAR(255) NOT NULL,
    Industry NVARCHAR(255) NOT NULL,
    Country NVARCHAR(255) NOT NULL,
    Internal_Audit INT NOT NULL,
    Company_Size NVARCHAR(255) NOT NULL, 
    Using_Solution NVARCHAR(255) NOT NULL,
    Email NVARCHAR(255) NOT NULL,
    Score INT,
    Question_Id INT FOREIGN KEY REFERENCES Questions(id),
);