SELECT * FROM Users;
ALTER TABLE Questions
ADD Category VARCHAR(255);

SELECT * FROM Questions;

CREATE TABLE UserScores (
    id INTEGER PRIMARY KEY IDENTITY(1,1),
    user_id INTEGER,
    category TEXT,
    FOREIGN KEY(user_id) REFERENCES Users(id)score INTEGER,
    
);
SELECT * FROM UserScores
SELECT * FROM Countries


DELETE FROM Countries WHERE id = 81
INSERT INTO Countries(id, Name)
VALUES (81, 'Palestine');