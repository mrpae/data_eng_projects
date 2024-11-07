# Assigment
Read user data from an API

Using the https://randomuser.me/ API you would need to read in 100 users.
Mask or anonymize PII (Personally Identifiable Information)
Save the data as encrypted parquet files on Minio. The data should have a flat structure (no arrays or structs)
The following analytical questions should still be answerable with the data:

What is the average duration since a user registered?
What is the age and gender distribution of users?
Which location (country and city) do most users come from?

Reading:

https://medium.com/p/2b22466ae6ed
This is a general very simple tip on how to mask some data

https://duckdb.org/docs/data/parquet/encryption.html
DuckDB docs for encrypting parquet files

# Solution
Data from 100 random users were obtained by
`curl -X GET "https://randomuser.me/api/?results=100" -o rand_users100.json`

I also tried to automate uploading the json file to my S3 bucket by using
`docker cp rand_users100.json minio:/data/users/`
but it failed. After uploading the file manually, it can be seen that the .json file gets transformed into a folder that contains a .meta file. I guess the road for automation is slightly longer. :)



