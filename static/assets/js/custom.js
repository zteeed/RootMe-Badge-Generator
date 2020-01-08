function display_sw2(msg, title, type) {
  Swal.fire({
      type: type,
      title: title,
      html: msg,
  })
}
