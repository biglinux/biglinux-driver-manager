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

// Open or close Modal
$(function () {
  $(".status-button:not(.open)").on("click", function (e) {
    $(".overlay-app").addClass("is-active");
  });
  $(".pop-up .close").click(function () {
    $(".overlay-app").removeClass("is-active");
  });
});

$(".status-button:not(.open)").click(function () {
  $(".pop-up").addClass("visible");
});

$(".pop-up .close").click(function () {
  $(".pop-up").removeClass("visible");
});

$(function () {
  $(".status-button2:not(.open)").on("click", function (e) {
    $(".overlay-app").addClass("is-active");
  });
  $(".pop-up2 .close").click(function () {
    $(".overlay-app").removeClass("is-active");
  });
});

$(".status-button2:not(.open)").click(function () {
  $(".pop-up2").addClass("visible");
});

$(".pop-up2 .close").click(function () {
  $(".pop-up2").removeClass("visible");
});


$(function () {
  $(".status-button3:not(.open)").on("click", function (e) {
    $(".overlay-app").addClass("is-active");
  });
  $(".pop-up3 .close").click(function () {
    $(".overlay-app").removeClass("is-active");
  });
});

$(".status-button3:not(.open)").click(function () {
  $(".pop-up3").addClass("visible");
});

$(".pop-up3 .close").click(function () {
  $(".pop-up3").removeClass("visible");
});

// Sort List <ul> <li>
sortList(document.getElementsByClassName('list')[0]);

function sortList(ul){
    var new_ul = ul.cloneNode(false);

    // Add all lis to an array
    var lis = [];
    for(var i = ul.childNodes.length; i--;){
        if(ul.childNodes[i].nodeName === 'LI')
            lis.push(ul.childNodes[i]);
    }

    // Sort the lis in descending order
    lis.sort(function(a, b){
       return parseInt(b.childNodes[0].data , 10) - 
              parseInt(a.childNodes[0].data , 10);
    });

    // Add them into the ul in order
    for(var i = 0; i < lis.length; i++)
        new_ul.appendChild(lis[i]);
    ul.parentNode.replaceChild(new_ul, ul);
}

