# Assigment
Read user data from an API

Using the https://randomuser.me/ API you would need to read in 100 users.
Mask or anonymize PII (Personally Identifiable Information)
Save the data as encrypted parquet files on Minio. The data should have a flat structure (no arrays or structs)
The following analytical questions should still be answerable with the data:

* What is the average duration since a user registered?
* What is the age and gender distribution of users?
* Which location (country and city) do most users come from?

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

The "heavy" part of my solution is in `scripts/script.py`.
* I decided to unnest the users list (otherwise I simply had one row of data) and after flattening the data into separate columns, I loaded it to a Pandas dataframe so I could manipulate it more easily.
* I created different functions for masking data: one for names, one for numbers, one for emails, and one for websites. I think I covered all of the PII and it would be really difficult to identify anyone based on the visible part. Also I am sure that the analytical questions can be provided even after masking. For example, `print(f"The average duration since a user registered: {conn.sql("select sum(registered_age)/count(registered_age) as avg from secure_users")}")` answers the first question.
* A table called `secure_users` is created based on the masked dataframe.
* `conn.execute(f"PRAGMA add_parquet_key('key128', '{os.getenv("PARQUET_ENCRYPTION_KEY")}');")` generates a 128-bit encryption key.
* `conn.sql("COPY secure_users TO 's3://users/users_secure.parquet' (FORMAT PARQUET, ENCRYPTION_CONFIG {footer_key: 'key128'});")` saves the encrypted parquet files on Minio.

It can be later checked that 
```
conn.sql("SELECT * FROM read_parquet('s3://users/users_secure.parquet')")
```
returns an error because there is no encryption key. However, if we pass it with
```
conn.sql("SELECT * FROM read_parquet('s3://users/users_secure.parquet', encryption_config = {footer_key: 'key128'})")
```
then we have normal access to the masked data.


# Usage

1. After pulling the repository, run `docker compose up -d`. 
2. Open [localhost:9001](`http://localhost:9001/browser/users`) and insert access credentials that are specified in your `.env` file.
3. Upload `rand_users100.json` to the `users` bucket.
4. In your command line, attach to the duckdb's container `docker exec -it duckdb bash`.
5. Move to the `scripts` folder `cd scripts`.
6. Launch the python script: `python script.py`

After the final step, you are supposed to see the encrypted parquet file in `s3://users`. This can be easily accessed in duckdb, but only with an encryption key:
```python
print(conn.sql("SELECT * FROM read_parquet('s3://users/users_secure.parquet', encryption_config = {footer_key: 'key128'})"))
```