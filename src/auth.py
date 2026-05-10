"""Authentication utilities for Streamlit app."""

import streamlit as st
from src.database import authenticate_user, create_user, get_user_by_email, User


def init_session_state():
    """Initialize session state variables."""
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False


def login_page():
    """Display login/signup page."""
    st.set_page_config(page_title="Fraud Detection System", layout="wide")
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("# Fraud Detection System")
        st.markdown("---")

        # Tab for login/signup
        tab1, tab2 = st.tabs(["Login", "Sign Up"])

        with tab1:
            st.markdown("### Login")
            email = st.text_input("Email", key="login_email", placeholder="your@email.com")
            password = st.text_input("Password", type="password", key="login_password")

            if st.button("Login", key="login_button", use_container_width=True):
                if not email or not password:
                    st.error("Please enter email and password")
                else:
                    user = authenticate_user(email, password)
                    if user:
                        st.session_state.user_id = user.id
                        st.session_state.user_email = user.email
                        st.session_state.authenticated = True
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password")

        with tab2:
            st.markdown("### Create Account")
            new_email = st.text_input("Email", key="signup_email", placeholder="your@email.com")
            new_password = st.text_input(
                "Password", type="password", key="signup_password", placeholder="At least 8 characters"
            )
            confirm_password = st.text_input(
                "Confirm Password", type="password", key="signup_confirm", placeholder="Repeat password"
            )

            if st.button("Sign Up", key="signup_button", use_container_width=True):
                if not new_email or not new_password:
                    st.error("Please fill in all fields")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    # Check if user exists
                    if get_user_by_email(new_email):
                        st.error("Email already registered. Please login or use a different email.")
                    else:
                        try:
                            user = create_user(new_email, new_password)
                            st.success("Account created successfully! You can now login.")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error creating account: {str(e)}")

        st.markdown("---")
        st.caption("Your data is secure. Passwords are hashed with bcrypt.")


def logout():
    """Logout user."""
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.authenticated = False
    st.rerun()


def require_auth():
    """Decorator to require authentication. Returns True if authenticated, False otherwise."""
    init_session_state()
    return st.session_state.authenticated


def get_current_user_id() -> int | None:
    """Get current logged-in user ID."""
    return st.session_state.get("user_id")


def get_current_user_email() -> str | None:
    """Get current logged-in user email."""
    return st.session_state.get("user_email")
