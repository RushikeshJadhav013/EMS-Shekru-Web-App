import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  Phone, 
  Mail, 
  MapPin, 
  Clock, 
  MessageCircle, 
  Headphones,
  ArrowLeft,
  ExternalLink
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const ContactSupport: React.FC = () => {
  const navigate = useNavigate();

  const contactMethods = [
    {
      icon: Phone,
      title: '24/7 Phone Support',
      description: 'Call us anytime for immediate assistance',
      details: ['+91 9975072250', '+91 8485050671'],
      action: 'tel:+919975072250',
      actionLabel: 'Call Now',
      color: 'blue'
    },
    {
      icon: MessageCircle,
      title: 'WhatsApp Support',
      description: 'Chat with us on WhatsApp for quick help',
      details: ['+91 9975072250'],
      action: 'https://wa.me/919975072250?text=Hello,%20I%20need%20help%20with%20Shekru%20Web',
      actionLabel: 'Open WhatsApp',
      color: 'green'
    },
    {
      icon: Mail,
      title: 'Email Support',
      description: 'Send us an email and we\'ll respond within 24 hours',
      details: ['support@shekrulabs.com'],
      action: 'mailto:support@shekrulabs.com',
      actionLabel: 'Send Email',
      color: 'purple'
    }
  ];

  const handleWhatsApp = () => {
    window.open('https://wa.me/919975072250?text=Hello,%20I%20need%20help%20with%20Shekru%20Web', '_blank');
  };

  const handleCall = (number: string) => {
    window.location.href = `tel:${number}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 relative overflow-hidden">
      {/* Decorative Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-200/30 rounded-full blur-3xl"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-indigo-200/30 rounded-full blur-3xl"></div>
      </div>

      <div className="relative z-10 container mx-auto px-4 py-12">
        {/* Back Button */}
        <Button
          variant="ghost"
          onClick={() => navigate('/login')}
          className="mb-6 hover:bg-white/50"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Login
        </Button>

        {/* Header */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl blur-lg opacity-60"></div>
              <div className="relative h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-xl">
                <Headphones className="h-8 w-8 text-white" />
              </div>
            </div>
          </div>
          <h1 className="text-4xl font-bold text-slate-800 mb-3">
            We're Here to Help
          </h1>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Our support team is available 24/7 to assist you with any questions or issues
          </p>
        </div>

        {/* Contact Methods Grid */}
        <div className="grid md:grid-cols-3 gap-6 mb-12 max-w-6xl mx-auto">
          {contactMethods.map((method, index) => {
            const Icon = method.icon;
            const colorClasses = {
              blue: 'bg-blue-100 text-blue-600 border-blue-200',
              green: 'bg-green-100 text-green-600 border-green-200',
              purple: 'bg-purple-100 text-purple-600 border-purple-200'
            };

            return (
              <Card key={index} className="bg-white/80 backdrop-blur-xl border-white/20 shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105">
                <CardHeader>
                  <div className={`h-14 w-14 rounded-2xl ${colorClasses[method.color as keyof typeof colorClasses]} flex items-center justify-center mb-4 border-2`}>
                    <Icon className="h-7 w-7" />
                  </div>
                  <CardTitle className="text-xl text-slate-800">{method.title}</CardTitle>
                  <CardDescription className="text-slate-600">
                    {method.description}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    {method.details.map((detail, idx) => (
                      <p key={idx} className="text-slate-700 font-semibold text-lg">
                        {detail}
                      </p>
                    ))}
                  </div>
                  <Button
                    onClick={() => window.open(method.action, method.icon === MessageCircle ? '_blank' : '_self')}
                    className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
                  >
                    {method.actionLabel}
                    <ExternalLink className="h-4 w-4 ml-2" />
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Quick WhatsApp Button */}
        <div className="max-w-2xl mx-auto mb-12">
          <Card className="bg-gradient-to-r from-green-500 to-emerald-600 border-0 shadow-2xl">
            <CardContent className="p-8 text-center text-white">
              <MessageCircle className="h-12 w-12 mx-auto mb-4" />
              <h3 className="text-2xl font-bold mb-2">Quick WhatsApp Support</h3>
              <p className="mb-6 text-green-50">
                Get instant help via WhatsApp - Available 24/7
              </p>
              <Button
                onClick={handleWhatsApp}
                size="lg"
                className="bg-white text-green-600 hover:bg-green-50 font-semibold text-lg px-8"
              >
                <MessageCircle className="h-5 w-5 mr-2" />
                Chat on WhatsApp
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Company Information */}
        <div className="max-w-4xl mx-auto">
          <Card className="bg-white/80 backdrop-blur-xl border-white/20 shadow-xl">
            <CardHeader>
              <CardTitle className="text-2xl text-slate-800 flex items-center gap-2">
                <MapPin className="h-6 w-6 text-blue-600" />
                Company Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid md:grid-cols-2 gap-6">
                {/* Company Details */}
                <div className="space-y-4">
                  <div>
                    <h4 className="font-semibold text-slate-700 mb-2">Company Name</h4>
                    <p className="text-slate-600 text-lg">Shekru Labs India PVT. LTD.</p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-700 mb-2">Location</h4>
                    <p className="text-slate-600 flex items-start gap-2">
                      <MapPin className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                      <span>Pune, Maharashtra, India</span>
                    </p>
                  </div>
                </div>

                {/* Contact Details */}
                <div className="space-y-4">
                  <div>
                    <h4 className="font-semibold text-slate-700 mb-2 flex items-center gap-2">
                      <Phone className="h-4 w-4 text-blue-600" />
                      Contact Numbers
                    </h4>
                    <div className="space-y-2">
                      <button
                        onClick={() => handleCall('+919975072250')}
                        className="block text-blue-600 hover:text-blue-700 font-medium hover:underline"
                      >
                        +91 9975072250
                      </button>
                      <button
                        onClick={() => handleCall('+918485050671')}
                        className="block text-blue-600 hover:text-blue-700 font-medium hover:underline"
                      >
                        +91 8485050671
                      </button>
                    </div>
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-700 mb-2 flex items-center gap-2">
                      <Clock className="h-4 w-4 text-blue-600" />
                      Support Hours
                    </h4>
                    <p className="text-slate-600">24/7 - Always Available</p>
                  </div>
                </div>
              </div>

              {/* Additional Info */}
              <div className="pt-6 border-t border-slate-200">
                <div className="bg-blue-50 rounded-xl p-4 border border-blue-100">
                  <p className="text-sm text-slate-700">
                    <strong className="text-blue-700">Note:</strong> For urgent issues, we recommend using WhatsApp or calling us directly. 
                    Our support team typically responds to emails within 24 hours during business days.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* FAQ Section */}
        <div className="max-w-4xl mx-auto mt-12">
          <h2 className="text-2xl font-bold text-slate-800 mb-6 text-center">
            Frequently Asked Questions
          </h2>
          <div className="grid md:grid-cols-2 gap-4">
            <Card className="bg-white/60 backdrop-blur-sm border-white/20">
              <CardHeader>
                <CardTitle className="text-lg text-slate-800">How do I reset my password?</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600 text-sm">
                  Contact our support team via WhatsApp or phone, and we'll help you reset your password securely.
                </p>
              </CardContent>
            </Card>

            <Card className="bg-white/60 backdrop-blur-sm border-white/20">
              <CardHeader>
                <CardTitle className="text-lg text-slate-800">What are your support hours?</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600 text-sm">
                  Our support team is available 24/7 to assist you with any questions or technical issues.
                </p>
              </CardContent>
            </Card>

            <Card className="bg-white/60 backdrop-blur-sm border-white/20">
              <CardHeader>
                <CardTitle className="text-lg text-slate-800">How quickly will I get a response?</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600 text-sm">
                  WhatsApp and phone support: Immediate. Email support: Within 24 hours during business days.
                </p>
              </CardContent>
            </Card>

            <Card className="bg-white/60 backdrop-blur-sm border-white/20">
              <CardHeader>
                <CardTitle className="text-lg text-slate-800">Can I schedule a demo?</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600 text-sm">
                  Yes! Contact us via WhatsApp or phone to schedule a personalized demo of our platform.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ContactSupport;
