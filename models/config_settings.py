from odoo import models, fields, api

class ANPRSubscriptionConfig(models.Model):
    _name = 'anpr.subscription.config'
    _description = 'Configuration des Abonnements ANPR'

    # Paramètres de connexion distante
    remote_odoo_url = fields.Char(string="URL Odoo distant", required=True)
    remote_odoo_db = fields.Char(string="Base de données distante", required=True)
    remote_odoo_login = fields.Char(string="Utilisateur distant", required=True)
    remote_odoo_password = fields.Char(string="Mot de passe distant", required=True)
    remote_odoo_prefix = fields.Char(string="Préfixe des écritures", default="[DISTANT]")

    @api.model
    def get_config(self):
        """Récupère la configuration active"""
        return self.search([], limit=1)

    def set_config(self, vals):
        """Met à jour ou crée la configuration"""
        config = self.get_config()
        if config:
            config.write(vals)
        else:
            config = self.create(vals)
        return config