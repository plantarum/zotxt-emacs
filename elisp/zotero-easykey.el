(require 'zotero)

(defvar zotero-easykey-regex
  "@\\([[:alnum:]]+\\)")

(defvar zotero-easykey-mode-map
  (let ((map (make-sparse-keymap)))
    (define-key map [(control c) (z) (o)] 'zotero-easykey-select-item-at-point)
    map))

(defun zotero-easykey-at-point ()
  "Return the value of the easykey at point. Easykey must start
with a @ to be recognized, but this will *not* be returned."
  (save-excursion
    (while (and (not (looking-at zotero-easykey-regex))
                (looking-at "[[:alnum:]]"))
      (backward-char))
    (if (looking-at zotero-easykey-regex)
        (match-string 1)
      nil)))

(defun zotero-easykey-url-retrieve (raw-url)
  (save-excursion
    (let* ((url (url-encode-url raw-url))
           (buff (url-retrieve-synchronously url)))
      (set-buffer buff)
      (url-http-parse-response)
      (if (not (eq 200 url-http-response-status))
          nil
        (with-temp-buffer
          (url-insert buff)
          (beginning-of-buffer)
          (json-read))))))
  
(defun zotero-easykey-get-item-id-at-point ()
  "Return the Zotero ID of the item referred to by the easykey at
point, or nil."
  (save-excursion
    (let ((key (zotero-easykey-at-point)))
      (if (null key)
          nil
        (let* ((url (format "http://localhost:23119/zotxt/items?format=key&easykey=%s" key))
               (response (zotero-easykey-url-retrieve url)))
          (if (null response)
              nil
            (elt response 0)))))))

(defun zotero-easykey-select-item-at-point ()
  "Select the item referred to by the easykey at point in Zotero."
  (interactive)
  (let ((item-id (zotero-easykey-get-item-id-at-point)))
    (if item-id
        (browse-url (format "zotero://select/items/%s" item-id))
      (error "No item found!"))))

(define-minor-mode zotero-easykey-mode
  "Toggle zotero-easykey-mode.
With no argument, this command toggles the mode.
Non-null prefix argument turns on the mode.
Null prefix argument turns off the mode.

This is a minor mode for managing your citations with Zotero in a
org-mode document."  
  nil
  "Zotero"
  zotero-easykey-mode-map)

(provide 'zotero-easykey)
