import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import os

conn = duckdb.connect() # use duckdb.co
conn.install_extension("httpfs")
conn.load_extension("httpfs")
conn.sql(f"""
SET s3_region='us-east-1';
SET s3_url_style='path';
SET s3_endpoint='minio:9000';
SET s3_access_key_id='{os.getenv("MINIO_ROOT_USER")}' ;
SET s3_secret_access_key='{os.getenv("MINIO_ROOT_PASSWORD")}';
SET s3_use_ssl=false;
""")

def mask_name(name):
    # keeps at most 2 characters of the original name
    if name is None:
        return None
    if len(name) > 2:
        return name[0]+max(0,len(name)-2)*"*" + name[-1]
    elif len(name) == 2:
        return name[0] + "*"
    else:
        return name
    
def mask_email(email):
    # masks most of the email before @-symbol
    if email is None or "@" not in email:
        return None
    else:
        parts = email.split("@")
        parts[0] = mask_name(parts[0])
        return "@".join(parts)

def mask_number(phone_nr, last_digits=3):
    # masks every digit, except last three
    if phone_nr is None:
        return None
    else:
        charlst = list(str(phone_nr))
        for i in range(len(charlst)-last_digits):
            if charlst[i].isdigit():
                charlst[i] = "*"
        return "".join(charlst)

def mask_website(website):
    # I believe this is enough to hide sensitive info but to make sure that there is an actual website behind
    if website is None or "//" not in website:
        return None
    else:
        parts = website.split("//")
        pieces = parts[1].split("/")
        for i in range(len(pieces)):
            if i == 0:
                domainpieces = pieces[i].split(".")
                for j in range(len(domainpieces)):
                    if j != len(domainpieces) - 1:
                        domainpieces[j] = mask_name(domainpieces[j])
                pieces[i] = ".".join(domainpieces)
            elif i != len(pieces) - 1:
                pieces[i] = len(pieces[i]) * "*"
        parts[1] = "/".join(pieces)
        return "//".join(parts)

def secure_data(df):
    df["name_first"] = df["name_first"].apply(lambda x: mask_name(x))
    df["name_last"] = df["name_last"].apply(lambda x: mask_name(x))
    df["street_name"] = df["street_name"].apply(lambda x: mask_name(x))
    df["street_number"] = df["street_number"].apply(lambda x: mask_number(x, 1))
    df["email"] = df["email"].apply(lambda x: mask_email(x))
    df["latitude"] = pd.to_numeric(df["latitude"]).round()
    df["longitude"] = pd.to_numeric(df["longitude"]).round()
    df["dob_date"] = pd.to_datetime(df["dob_date"])
    df['dob_date'] = df['dob_date'].dt.strftime('%Y-%m-%d')
    df["username"] = df["username"].apply(lambda x: mask_name(x))
    df["phone"] = df["phone"].apply(lambda x: mask_number(x))
    df["cell"] = df["cell"].apply(lambda x: mask_number(x))
    df["id_name"] = df["id_name"].apply(lambda x: mask_name(x))
    df["id_value"] = df["id_value"].apply(lambda x: mask_name(x))
    df["picture_large"] = df["picture_large"].apply(lambda x: mask_website(x))
    df["picture_medium"] = df["picture_medium"].apply(lambda x: mask_website(x))
    df["picture_thumbnail"] = df["picture_thumbnail"].apply(lambda x: mask_website(x))
    return df

bucket_name = "users"
file_name = "rand_users100.json"
s3_url = f"s3://{bucket_name}/{file_name}"

conn.sql(f"""
    CREATE TABLE users AS
    SELECT result_item.unnest AS user_data
    FROM read_json_auto('{s3_url}')
    CROSS JOIN UNNEST(results) AS result_item
""")

masked_df = conn.execute("""
    SELECT 
        user_data.gender AS gender,
        user_data.name.title AS name_title,
        user_data.name.first AS name_first,
        user_data.name.last AS name_last,
        user_data.location.street.number AS street_number,
        user_data.location.street.name AS street_name,
        user_data.location.city AS city,
        user_data.location.state AS state,
        user_data.location.country AS country,
        user_data.location.postcode AS postcode,
        user_data.location.coordinates.latitude AS latitude,
        user_data.location.coordinates.longitude AS longitude,
        user_data.location.timezone.offset AS timezone_offset,
        user_data.location.timezone.description AS timezone_description,
        user_data.email AS email,
        user_data.login.uuid AS login_uuid,
        user_data.login.username AS username,
        user_data.dob.date AS dob_date,
        user_data.dob.age AS dob_age,
        user_data.registered.date AS registered_date,
        user_data.registered.age AS registered_age,
        user_data.phone AS phone,
        user_data.cell AS cell,
        user_data.id.name AS id_name,
        user_data.id.value AS id_value,
        user_data.picture.large AS picture_large,
        user_data.picture.medium AS picture_medium,
        user_data.picture.thumbnail AS picture_thumbnail,
        user_data.nat AS nationality
    FROM users
""").fetchdf()

conn.sql("DROP TABLE users")

print(masked_df)
masked_df = secure_data(masked_df)

conn.execute("create table secure_users as select * from masked_df")
print(conn.sql("select * from secure_users"))
print(f"The average duration since a user registered: {conn.sql("select sum(registered_age)/count(registered_age) as avg from secure_users")}")
conn.execute(f"PRAGMA add_parquet_key('key128', '{os.getenv("PARQUET_ENCRYPTION_KEY")}');")
conn.sql("COPY secure_users TO 's3://users/users_secure.parquet' (FORMAT PARQUET, ENCRYPTION_CONFIG {footer_key: 'key128'});")

try:
    print(conn.sql("SELECT * FROM read_parquet('s3://users/users_secure.parquet')"))
except:
    print("Cannot read encrypted data!")

print(conn.sql("SELECT * FROM read_parquet('s3://users/users_secure.parquet', encryption_config = {footer_key: 'key128'})"))