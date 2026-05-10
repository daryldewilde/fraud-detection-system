"""Authentication utilities for Streamlit app."""

import streamlit as st

from src.database import authenticate_user, change_user_password, get_user_by_email


def init_session_state():
    """Initialize session state variables."""
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = None
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "must_change_password" not in st.session_state:
        st.session_state.must_change_password = False


def login_page():
    """Display login page."""
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("# Fraud Detection System")
        st.markdown("---")

        st.markdown("### Login")
        st.caption("Accounts are created by an administrator. Contact your admin if you do not have access.")
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
                    st.session_state.user_role = user.role
                    st.session_state.authenticated = True
                    st.session_state.must_change_password = bool(user.force_password_change)
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid email or password")

        st.markdown("---")
        st.caption("Your data is secure. Passwords are hashed with bcrypt.")


def password_change_page():
    """Prompt the authenticated user to change their password."""
    st.title("Change Your Password")
    st.caption("This is required on your first login.")

    new_password = st.text_input("New Password", type="password", key="new_password")
    confirm_password = st.text_input("Confirm New Password", type="password", key="confirm_new_password")

    if st.button("Update Password", use_container_width=True):
        if not new_password or not confirm_password:
            st.error("Please fill in both password fields")
        elif len(new_password) < 8:
            st.error("Password must be at least 8 characters")
        elif new_password != confirm_password:
            st.error("Passwords do not match")
        else:
            try:
                change_user_password(st.session_state.user_id, new_password)
                st.session_state.must_change_password = False
                st.success("Password updated successfully")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not update password: {exc}")


def logout():
    """Logout user."""
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.user_role = None
    st.session_state.authenticated = False
    st.session_state.must_change_password = False
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


def get_current_user_role() -> str | None:
    """Get current logged-in user role."""
    return st.session_state.get("user_role")


def must_change_password() -> bool:
    """Return whether the current user must change password."""
    return bool(st.session_state.get("must_change_password"))
