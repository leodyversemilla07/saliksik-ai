from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import IntegrityError
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register a new user and return an authentication token.
    """
    try:
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not all([username, email, password]):
            return Response(
                {
                    'error': 'Missing required fields',
                    'details': 'Username, email, and password are required'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate password strength
        if len(password) < 8:
            return Response(
                {
                    'error': 'Password too weak',
                    'details': 'Password must be at least 8 characters long'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # Create token
        token, created = Token.objects.get_or_create(user=user)
        
        logger.info(f"New user registered: {username}")
        
        return Response(
            {
                'message': 'User created successfully',
                'token': token.key,
                'user_id': user.id,
                'username': user.username
            },
            status=status.HTTP_201_CREATED
        )
        
    except IntegrityError:
        return Response(
            {
                'error': 'User already exists',
                'details': 'A user with this username already exists'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return Response(
            {
                'error': 'Registration failed',
                'details': 'An error occurred during registration'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Authenticate user and return token.
    """
    try:
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {
                    'error': 'Missing credentials',
                    'details': 'Username and password are required'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        
        if user:
            token, created = Token.objects.get_or_create(user=user)
            logger.info(f"User logged in: {username}")
            
            return Response(
                {
                    'message': 'Login successful',
                    'token': token.key,
                    'user_id': user.id,
                    'username': user.username
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {
                    'error': 'Invalid credentials',
                    'details': 'Username or password is incorrect'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return Response(
            {
                'error': 'Login failed',
                'details': 'An error occurred during login'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def logout(request):
    """
    Logout user by deleting their token.
    """
    try:
        request.user.auth_token.delete()
        logger.info(f"User logged out: {request.user.username}")
        
        return Response(
            {'message': 'Logout successful'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return Response(
            {
                'error': 'Logout failed',
                'details': 'An error occurred during logout'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def profile(request):
    """
    Get user profile information.
    """
    try:
        user = request.user
        return Response(
            {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'date_joined': user.date_joined,
                'last_login': user.last_login
            },
            status=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return Response(
            {
                'error': 'Profile retrieval failed',
                'details': 'An error occurred while retrieving profile'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
