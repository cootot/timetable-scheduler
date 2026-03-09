from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db import models
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class GoogleLoginView(APIView):
    """
    Handle Google OAuth2 login with Gmail aliasing support.
    """
    permission_classes = [] # Allow anyone to try login

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Verify Google token
            # Note: In a real environment, use settings.GOOGLE_CLIENT_ID
            
            # Debug: Log client ID and first part of token
            logger.info(f"Attempting Google login for client: {settings.GOOGLE_CLIENT_ID}")
            token_prefix = token[:10] + "..." if token else "None"
            logger.info(f"Token prefix: {token_prefix}")

            try:
                # Add clock_skew tolerance (10 seconds) to handle server time differences
                idinfo = id_token.verify_oauth2_token(
                    token, 
                    requests.Request(), 
                    settings.GOOGLE_CLIENT_ID,
                    clock_skew_in_seconds=10
                )
            except ValueError as e:
                # If verification fails, try to peek at the audience to see if it's a mismatch
                import json
                import base64
                try:
                    # JWT is [header].[payload].[signature]
                    _, payload_b64, _ = token.split('.')
                    # Add padding if needed
                    payload_b64 += '=' * (-len(payload_b64) % 4)
                    payload_json = base64.b64decode(payload_b64).decode('utf-8')
                    payload = json.loads(payload_json)
                    logger.error(f"Google Token Verification Failed. Token Aud: {payload.get('aud')}, Expected Aud: {settings.GOOGLE_CLIENT_ID}")
                except Exception as peek_error:
                    logger.error(f"Could not peek at token payload: {str(peek_error)}")
                raise e
            
            email = idinfo['email']
            
            # 2. Check for aliasing logic
            # If the email is the master email (m3amrita@gmail.com), 
            # find all users whose email is an alias of it.
            
            # Get base email and domain
            if '+' in email:
                base_email_part, _ = email.split('+', 1)
                domain_part = email.split('@', 1)[1]
                base_email = f"{base_email_part}@{domain_part}"
            else:
                base_email = email
            
            # The user said "m3amrita@gmail.com" is the master.
            # Let's find all users that match the base email (either exactly or via aliasing)
            matched_users = User.objects.filter(
                models.Q(email=base_email) | 
                models.Q(email__startswith=f"{base_email.split('@')[0]}+")
            )

            # 3. If multiple users found, return them for selection
            # UNLESS they specified which user they want (second step)
            selected_user_id = request.data.get('selected_user_id')
            
            if matched_users.count() > 1 and not selected_user_id:
                user_list = []
                for u in matched_users:
                    user_list.append({
                        'id': u.id,
                        'username': u.username,
                        'role': u.role,
                        'display_name': u.first_name or u.username
                    })
                return Response({
                    'status': 'needs_selection',
                    'users': user_list
                })

            # 4. Finalize login for the selected or only user
            if selected_user_id:
                user = matched_users.get(id=selected_user_id)
            else:
                user = matched_users.first()

            if not user:
                return Response({'error': 'No corresponding user found in the system.'}, status=status.HTTP_404_NOT_FOUND)

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'first_name': user.first_name
                }
            })

        except ValueError as e:
            logger.error(f"Invalid Google Token: {str(e)}")
            return Response({'error': f'DEBUG_CANARY_V3_FIXED: Invalid Google Token: {str(e)}'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Google Login Error: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
