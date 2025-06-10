from odoo import models, fields, api

class SubscriptionPass(models.Model):
    _name = 'anpr.subscription.pass'
    _description = 'Abonnement Péage'

    name = fields.Char(string="Nom de l'abonné", required=True)
    user_id = fields.Many2one('res.users', string="Utilisateur lié", required=True)
    plate = fields.Char(string="Plaque d'immatriculation", required=True)
    balance = fields.Float(string="Solde du compte", required=True, default=0.0)
    cost_per_passage = fields.Float(string="Coût par passage", required=True, default=500.0)

    def debit_passage(self):
        """Déduit le coût du passage si le solde est suffisant"""
        for rec in self:
            if rec.balance >= rec.cost_per_passage:
                rec.balance -= rec.cost_per_passage
            else:
                raise UserError("Solde insuffisant pour ce passage.")