#!/usr/bin/env python3
"""
Creates an IAM user with read-only access to the S3 bucket for TTS audio files.
"""
import boto3
import json
import sys

def create_read_only_user():
    bucket_name = "ai-generated-audio-books-eu-west-1-wav"
    user_name = "tts-audio-reader"
    policy_name = "S3ReadOnlyPolicy"
    
    # Initialize IAM client
    iam = boto3.client('iam')
    
    try:
        # 1. Create IAM user
        print(f"Creating IAM user: {user_name}...")
        try:
            iam.create_user(UserName=user_name)
            print(f"✓ User '{user_name}' created successfully")
        except iam.exceptions.EntityAlreadyExistsException:
            print(f"✓ User '{user_name}' already exists")
        
        # 2. Create inline policy for read access to S3 bucket
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*"
                    ]
                }
            ]
        }
        
        print(f"Attaching read-only policy to '{user_name}'...")
        iam.put_user_policy(
            UserName=user_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        print(f"✓ Policy attached successfully")
        
        # 3. Create access key
        print(f"Creating access key for '{user_name}'...")
        
        # First, delete old access keys if any (max 2 keys per user)
        existing_keys = iam.list_access_keys(UserName=user_name)
        for key in existing_keys['AccessKeyMetadata']:
            print(f"  Deleting old access key: {key['AccessKeyId']}")
            iam.delete_access_key(
                UserName=user_name,
                AccessKeyId=key['AccessKeyId']
            )
        
        # Create new access key
        response = iam.create_access_key(UserName=user_name)
        access_key = response['AccessKey']
        
        print("\n" + "="*70)
        print("✓ IAM User Created Successfully!")
        print("="*70)
        print("\nCopy and paste the following into your terminal:\n")
        print(f"export AWS_ACCESS_KEY_ID={access_key['AccessKeyId']}")
        print(f"export AWS_SECRET_ACCESS_KEY={access_key['SecretAccessKey']}")
        print(f"export AWS_DEFAULT_REGION=eu-west-1")
        print("\n" + "="*70)
        print("\nOr add to your .envrc file:\n")
        print(f"export AWS_ACCESS_KEY_ID='{access_key['AccessKeyId']}'")
        print(f"export AWS_SECRET_ACCESS_KEY='{access_key['SecretAccessKey']}'")
        print(f"export AWS_DEFAULT_REGION='eu-west-1'")
        print("\n" + "="*70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    create_read_only_user()
