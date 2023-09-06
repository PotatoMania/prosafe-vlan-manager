# -*- encoding: utf-8 -*-

# when posting forms, use cgi, otherwise(get) use htm
# sometimes both will work on old firmwares
# on latest firmware, must post to cgi and get from htm.

# end with double period('.') indicates we should change the last
# dot to 'htm' or 'cgi' on demand.

SW_ROOT = '/'
SW_INDEX = '/index.htm'
SW_LOGIN = '/login..'
SW_LOGOUT = '/logout.cgi'

SW_FORM_RAND_ID = 'rand'
SW_FORM_HASH_ID = 'hash'
SW_FORM_ERRMSG_ID = 'err_msg'

# check if current password need change, not useful
# SW_PWD_CKL = '/pwd_ckl.htm'

SW_INFO = '/switch_info.htm'

SW_8021Q_CFG = '/8021qCf..'
SW_8021Q_MEMBERSHIP = '/8021qMembe..'
SW_8021Q_PVIDS = '/portPVID..'

SW_BACKUP = '/config_data.bin'
SW_RESTORE = '/restore_conf..'
SW_RESTORE_NOTICE = 'The device is restarting. Wait until the process is complete.'