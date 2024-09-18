SELECT * FROM Users;
ALTER TABLE Questions
ADD Category VARCHAR(255);

SELECT * FROM Questions;

CREATE TABLE UserScores (
    id INTEGER PRIMARY KEY IDENTITY(1,1),
    user_id INTEGER,
    category TEXT,
    score INTEGER,
    FOREIGN KEY(user_id) REFERENCES Users(id)
);
SELECT * FROM UserScores
SELECT * FROM Countries


DELETE FROM Countries WHERE id = 81
INSERT INTO Countries(id, Name)
VALUES (81, 'Palestine');