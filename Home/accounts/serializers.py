from rest_framework import serializers

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
User=get_user_model()



class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=('username','password','email','mobile_number')
        extra_kwargs={
            "password":{"write_only":True}
        }

    
    def validate(self, attrs):
        password=attrs.get('password')

        if len(password)<8:
            raise serializers.ValidationError("password length must be greater than 8")
        
        if not any(char in "@#$!%&*" for char in password):
            raise serializers.ValidationError("Password must include special character(@ #$!%&*)")
        

        if not any(char.isupper() for char in password):
            raise serializers.ValidationError("Must include a Upper case letter")
        
        return attrs
    


    def validate_email(self,value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Gmail already used by another person")
        
        return value
    


    def validate_mobile_number(self,value):
        if not len(value)==10 or not all(num.isdigit() for num in value):
            raise serializers.ValidationError("mobile number must contain 10 digit")
        
        return value





    
    def create(self, validated_data):
        user=User.objects.create_user(
           username=validated_data["username"],
           email=validated_data["email"],
           role="STUDENT",
           mobile_number=validated_data.get("mobile_number"),
           password=validated_data["password"],
        )

        user.save()

        return user
    




class CustomObtainPair_Serializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token=super().get_token(user)

        token['username']=user.username
        token['role']=user.role
        

        return token
    

    def validate(self, attrs):
        data= super().validate(attrs)


        data['username']=self.user.username
        data['role']=self.user.role


        return data