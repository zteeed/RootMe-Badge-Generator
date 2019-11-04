function display_sw2(msg, title, type) {
  Swal.fire({
      type: type,
      title: title,
      text: msg,
  })
}


function display_sw2_html(msg, title, type) {
  Swal.fire({
      type: type,
      title: title,
      html: msg,
  })
}
