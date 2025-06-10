# anpr_peage_subscription/models/subscription_pass.py
from odoo import models, fields, api
from odoo.exceptions import UserError

class SubscriptionPass(models.Model):
    _name = 'anpr.subscription.pass'
    _description = 'Abonnement Péage'

    name = fields.Char(string="Nom de l'abonné", required=True)
    plate = fields.Char(string="Plaque d'immatriculation", required=True)
    vehicle_type = fields.Selection([
        ('car',     'Car'),
        ('4x4',     '4x4 / SUV'),
        ('bus',     'Bus'),
        ('camion',  'Camion'),
        ('autres',  'Autres'),
    ], string="Type de véhicule", required=True)
    balance = fields.Float(string="Solde du compte", required=True, default=0.0)
    cost_per_passage = fields.Float(string="Coût par passage", required=True, default=500.0)

    def debit_passage(self):
        """Déduit le coût du passage si le solde est suffisant"""
        for rec in self:
            if rec.balance >= rec.cost_per_passage:
                rec.balance -= rec.cost_per_passage
            else:
                raise UserError("Solde insuffisant pour ce passage.")
