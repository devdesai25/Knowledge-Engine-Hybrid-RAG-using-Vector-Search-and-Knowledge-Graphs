from pydantic import BaseModel, EmailStr, Field, SecretStr

class UserSignup(BaseModel):
    email: EmailStr
    password: SecretStr = Field(...,min_length=8, description="user password")
    #        pattern=r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$