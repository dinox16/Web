const signUpButton = document.getElementById('signUp');
const signInButton = document.getElementById('signIn');
const container = document.getElementById('container');

if (signUpButton && signInButton && container) {
  signUpButton.addEventListener('click', () => {
    container.classList.add("right-panel-active");
  });

  signInButton.addEventListener('click', () => {
    container.classList.remove("right-panel-active");
  });
}
function showDialog(message) {
    document.getElementById('dialog-message').textContent = message;
    document.getElementById('dialog').style.display = 'flex';
}
document.getElementById('dialog-close').onclick = function() {
    document.getElementById('dialog').style.display = 'none';
};