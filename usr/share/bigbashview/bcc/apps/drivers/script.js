/* LEGENDA BOX STATUS BAR */
$(".box-items").mouseover(function () {
  $(this).children("#box-status-bar").css("display", "block");
});

$(".box-items").mouseout(function () {
  $(this).children("#box-status-bar").css("display", "none");
});

/* FIM LEGENDA BOX STATUS BAR */

$(document).on("click", "#point-container", function () {
  var show = $(this).data("show");
  $(show).removeClass("hide").siblings().addClass("hide");
});

$(function () {
  $(".menu-link").click(function () {
    $(".menu-link").removeClass("is-active");
    $(this).addClass("is-active");
  });
});

$(function () {
  $(".main-header-link").click(function () {
    $(".main-header-link").removeClass("is-active");
    $(this).addClass("is-active");
  });
});

const dropdowns = document.querySelectorAll(".dropdown");
dropdowns.forEach((dropdown) => {
  dropdown.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdowns.forEach((c) => c.classList.remove("is-active"));
    dropdown.classList.add("is-active");
  });
});

$(".search-bar input")
  .focus(function () {
    $(".header").addClass("wide");
  })
  .blur(function () {
    $(".header").removeClass("wide");
  });

const toggleButton = document.querySelector(".dark-light");

toggleButton.addEventListener("click", () => {
  document.body.classList.toggle("light-mode");
  _run('/usr/share/bigbashview/bcc/shell/setbgcolor.sh "' + document.body.classList.contains('light-mode') + '"');
});

var modals = document.getElementsByClassName("modal");
var modalOpenBtn = document.getElementsByClassName("modalOpenBtn");
var currentModal = null;

// Function to open modal by id
function openModal(id) {
  for (i = 0; i < modals.length; i++) {
    if (modals[i].getAttribute('id') == id) {
      currentModal = modals[i];
      currentModal.style.display = "block";
      break;
    }
  }
}

// When the user clicks the button, open modal with the same id
modalOpenBtn.onclick = function() {
  let currentID = modalOpenBtn.getAttribute('id');
  openModal(currentID);
}

// When the user clicks anywhere outside of the modal or the X, close
window.onclick = function(event) {
  if (event.target == currentModal || event.target.getAttribute('class') == 'modalClose') {
    currentModal.style.display = "none";
  }
}


//Fecha welcome
$(function () {
  $(".content-wrapper-header .close").click(function () {
    $("#welcome").css("display", "none");
  }); 
});

var bigcount = 1;
$('#btn-big').click(function(){
    if (bigcount >= 3 && bigcount <= 3) {
      $('#welcome').css('display','flex');
    } else if (bigcount >= 6 && bigcount <= 6) {
      $('body').css('background-image', 'url("/usr/share/bigbashview/bcc/apps/big-store/img/body-bg.jpg")');
    } else if (bigcount >= 9) {
      window.location = "/usr/share/bigbashview/bcc/apps/big-store/.javascript-racer-master/racer.sh.htm";
    }
    ++bigcount;
});
