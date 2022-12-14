# © 2015 Compassion CH (Nicolas Tran)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, api, exceptions, _
import logging
import base64

_logger = logging.getLogger(__name__)


class FdsKeyGeneratorWizard(models.TransientModel):
    """ FDS Postfinance keys generator wizard.
        The goal is to generate and save in the database a pair key using RSA
        with the private key crypted

        This wizard is called when we click on "generate FDS authentication
        keys" for one FDS.
    """
    _name = 'fds.key.generator.wizard'
    _description = 'FDS key generator wizard'

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        required=True,
        help='assign the key to the user selected'
    )
    fds_authentication_keys_id = fields.Many2one(
        comodel_name='fds.authentication.keys',
        string='FDS authentication keys',
        readonly=True,
        help='[info] keep one recored of the model fds_authentication_key'
    )
    user_name = fields.Char(
        related='fds_authentication_keys_id.user_id.name',
        readonly=True,
        help='user previously selected'
    )
    public_key = fields.Binary(
        # string='Public key',
        related='fds_authentication_keys_id.public_key',
        readonly=True,
        help='public key generated'
    )
    private_key_crypted = fields.Binary(
        # string='Private key crypted',
        related='fds_authentication_keys_id.private_key_crypted',
        readonly=True,
        help='private key crypted generated'
    )
    pub_filename = fields.Char(
        string='Public key Filename',
        related='fds_authentication_keys_id.pub_filename',
        readonly=True,
        help='public key filename'
    )
    ppk_filename = fields.Char(
        string='Private key Filename',
        related='fds_authentication_keys_id.ppk_filename',
        readonly=True,
        help='private key filename'
    )
    state = fields.Selection(
        selection=[('default', 'Default'),
                   ('generate', 'Generate'),
                   ('done', 'Done')],
        readonly=True,
        default='default',
        help='[Info] keep state of the wizard'
    )

    ##################################
    #         Button action          #
    ##################################
    
    def generate_keys_button(self):
        """ Generate public and private crypted key then save in the database.
            Called by pressing generate button.

            :returns action: configuration for the next wizard's view
        """
        self.ensure_one()

        userkey = self.userkey_exist()
        keys = userkey.generate_pairkey()
        self.savekeys(keys[0], keys[1])
        self._state_generate_on()

        return self._do_populate_tasks()

    
    def confirm_keys_button(self):
        """ Confirm the generated keys.
            Called by pressing confirm button.

            :returns action: configuration for the next wizard's view
        """
        self.ensure_one()
        self._state_done_on()
        return self._do_populate_tasks()

    
    def cancel_keys_button(self):
        """ Remove public and private key saved in the database.
            Called by pressing cancel button.

            :returns action: close the wizard's view
        """
        self.ensure_one()
        self.fds_authentication_keys_id.unlink()
        return self._close_wizard()

    
    def send_keys_button(self):
        """ Send the public key to the FDS Postfinance by mail which will allow
            the selected user to connect to the SFTP using his private key.
            Called by pressing send button.
        """
        self.ensure_one()
        ############################
        # [TODO]
        # implement function to send
        raise exceptions.Warning(
            _('Not implemented yet, download public key and send the email to'
              ' postfinance manually.'))

    ##############################
    #          function          #
    ##############################
    
    def savekeys(self, public_key, private_key_crypted):
        """ Save in the database the public and private creyted key

            :param str public_key: generate by RSA
            :param str private_key_crypted: generate and crypted by RSA
            :returns action:  None
            :raises Warning:
                - if the state of the wizard do not exist
                - if more than one FDS account selected
        """
        self.ensure_one()

        # depending on state
        if self.state == 'default':

            # recup selected fds_postfiance_account id
            active_ids = self.env.context.get('active_ids')
            if len(active_ids) != 1:
                raise exceptions.Warning(_('Select only one FDS account'))
            if isinstance(public_key, str):
                public_key = public_key.encode('ascii')
            if isinstance(private_key_crypted, str):
                private_key_crypted = private_key_crypted.encode('ascii')

            values = {
                'user_id': self.user_id.id,
                'fds_account_id': active_ids[0],
                'public_key': base64.b64encode(public_key),
                'private_key_crypted': base64.b64encode(private_key_crypted),
                'pub_filename': self._generate_filename('PublicKey', 'pub'),
                'ppk_filename': self._generate_filename('PrivateKey', 'ppk')
            }
            fds_authentication_keys_obj = self.env['fds.authentication.keys']
            keys = fds_authentication_keys_obj.create(values)
            self.write({'fds_authentication_keys_id': keys.id})

        elif self.state == 'generate':
            self.fds_authentication_keys_id.write({
                'public_key': base64.b64encode(public_key),
                'private_key_crypted':  base64.b64encode(private_key_crypted)})

        else:
            _logger.error("Bad implementation in fds_key_generator_wizard")
            raise exceptions.Warning(_('Error code. Contact your admin'))

    
    def userkey_exist(self):
        """ check if the authentication key already exist for the selected user

            :returns record: record of the model fds.authentication.keys
            :raises Warning: if user has already a key
        """
        self.ensure_one()

        current_fds_id = self.env.context.get('active_id')
        userkey_exist = self.env['fds.authentication.keys'].search([
            ['user_id', '=', self.user_id.id],
            ['fds_account_id', '=', current_fds_id]])

        if userkey_exist and self.state == 'default':
            raise exceptions.Warning(_('User keys already exist'))

        return userkey_exist

    
    def _generate_filename(self, prefix='Unknow name key', suffix='nothing'):
        """ private function that generate the name of the key file.

            :param str prefix: prefix of the name ("PrivateKey" or "PublicKey")
            :param str suffix: suffix of the name ("pub" or "ppk")
            :returns str: filename
        """
        self.ensure_one()
        fds_account = self.env[self.env.context.get('active_model')]
        fds_name = fds_account.browse(self.env.context.get('active_ids')).name
        user_name = self.user_id.name
        filename = '%s_%s_%s.%s' % (prefix, fds_name, user_name, suffix)
        return filename

    
    def _state_generate_on(self):
        """ private function that change stat to generate

            :returns: None
        """
        self.state = 'generate'

    
    def _state_done_on(self):
        """ private function that change state to done

            :returns: None
        """
        self.state = 'done'

    
    def _do_populate_tasks(self):
        """ private function that continue with the same wizard.

            :returns action: configuration for the next wizard's view
        """
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'target': 'new',
        }

    
    def _close_wizard(self):
        """ private function that put action wizard to close

            :returns action: close the wizard's view
        """
        return {'type': 'ir.actions.act_window_close'}
