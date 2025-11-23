'use client'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ArrowRight, Scale, Users, Mail, CheckCircle } from 'lucide-react'
import Link from 'next/link'

export default function Home() {
  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="border-b border-gray-200">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Scale className="w-8 h-8 text-[#8B9D7F]" />
            <span className="text-2xl font-bold text-black">LawlyAI</span>
          </div>
          <Link href="/search">
            <Button className="bg-[#8B9D7F] hover:bg-[#7A8C6E] text-white">
              Try Now
            </Button>
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl md:text-6xl font-bold text-black mb-6">
            Find the Perfect Lawyer for Your Case
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Let AI connect you with the right legal expert. We contact lawyers on your behalf and find the best match for your situation.
          </p>
          <Link href="/search">
            <Button size="lg" className="bg-[#8B9D7F] hover:bg-[#7A8C6E] text-white text-lg px-8 py-6">
              Get Started <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
          </Link>
        </div>
      </section>

      {/* About Us Section */}
      <section className="bg-[#F5F7F3] py-20">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-4xl font-bold text-black text-center mb-12">
              Why We Built LawlyAI
            </h2>
            
            <div className="bg-white rounded-lg p-8 mb-8 shadow-sm">
              <p className="text-lg text-gray-700 leading-relaxed mb-6">
                Finding the right lawyer can be overwhelming and time-consuming. You might spend hours researching, making phone calls, and sending emails, only to find out a lawyer doesn't handle your type of case or isn't available.
              </p>
              <p className="text-lg text-gray-700 leading-relaxed mb-6">
                <span className="font-semibold text-black">We experienced this frustration firsthand.</span> That's why we created LawlyAI - to simplify the process and save you valuable time and stress.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6 mb-12">
              <Card className="border-[#8B9D7F] border-2">
                <CardContent className="pt-6">
                  <Mail className="w-12 h-12 text-[#8B9D7F] mb-4" />
                  <h3 className="text-xl font-bold text-black mb-2">Automated Outreach</h3>
                  <p className="text-gray-600">
                    Our AI contacts multiple lawyers on your behalf, saving you hours of manual work.
                  </p>
                </CardContent>
              </Card>

              <Card className="border-[#8B9D7F] border-2">
                <CardContent className="pt-6">
                  <Users className="w-12 h-12 text-[#8B9D7F] mb-4" />
                  <h3 className="text-xl font-bold text-black mb-2">Best Match</h3>
                  <p className="text-gray-600">
                    Get matched with lawyers who specialize in your specific legal situation.
                  </p>
                </CardContent>
              </Card>

              <Card className="border-[#8B9D7F] border-2">
                <CardContent className="pt-6">
                  <CheckCircle className="w-12 h-12 text-[#8B9D7F] mb-4" />
                  <h3 className="text-xl font-bold text-black mb-2">Transparent Communication</h3>
                  <p className="text-gray-600">
                    See all conversations between our AI and lawyers in one place.
                  </p>
                </CardContent>
              </Card>
            </div>

            <div className="bg-[#8B9D7F] text-white rounded-lg p-8 text-center">
              <h3 className="text-2xl font-bold mb-4">How LawlyAI Helps You</h3>
              <ul className="text-left max-w-2xl mx-auto space-y-3">
                <li className="flex items-start gap-3">
                  <CheckCircle className="w-6 h-6 mt-0.5 flex-shrink-0" />
                  <span className="text-lg">Save time by letting AI handle initial lawyer outreach</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle className="w-6 h-6 mt-0.5 flex-shrink-0" />
                  <span className="text-lg">Get responses from multiple qualified lawyers quickly</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle className="w-6 h-6 mt-0.5 flex-shrink-0" />
                  <span className="text-lg">Make informed decisions with complete transparency</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle className="w-6 h-6 mt-0.5 flex-shrink-0" />
                  <span className="text-lg">Focus on your case, not on finding representation</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-4 py-20">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-black mb-6">
            Ready to Find Your Lawyer?
          </h2>
          <p className="text-xl text-gray-600 mb-8">
            Describe your situation and let LawlyAI do the rest.
          </p>
          <Link href="/search">
            <Button size="lg" className="bg-[#8B9D7F] hover:bg-[#7A8C6E] text-white text-lg px-8 py-6">
              Try Now <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-50 border-t border-gray-200 py-8">
        <div className="container mx-auto px-4 text-center text-gray-600">
          <p>© 2025 LawlyAI. Connecting you with the right legal representation.</p>
        </div>
      </footer>
    </div>
  )
}