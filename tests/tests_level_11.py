import hedy
import textwrap
from tests_level_01 import HedyTester

class TestsLevel11(HedyTester):
  level = 11
  
  def test_print(self):
    result = hedy.transpile("print 'ik heet'", self.level)
    expected = "print('ik heet')"
    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  # def test_print_with_var(self):
  #   code = "naam is Hedy\nprint('ik heet' naam)"
  #   expected = "naam = 'Hedy'\nprint('ik heet'+str(naam))"
  #
  #   self.multi_level_tester(
  #     max_level=18,
  #     code=code,
  #     expected=expected,
  #     extra_check_function=self.is_not_turtle(),
  #     test_name=self.name()
  #   )
  def test_assign_print(self):
    #todo can be merged with 2 to 4 when we have f strings everywhere
    code = textwrap.dedent("""\
    naam is Hedy
    print 'ik heet' naam""")

    expected = textwrap.dedent("""\
    naam = 'Hedy'
    print('ik heet'+str(naam))""")

    self.multi_level_tester(
      max_level=10,
      code=code,
      expected=expected,
      extra_check_function=self.is_not_turtle(),
      test_name=self.name()
    )

  def test_print_with_calc_no_spaces(self):
    result = hedy.transpile("print '5 keer 5 is ' 5*5", self.level)
    expected = "print('5 keer 5 is '+str(int(5) * int(5)))"
    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  def test_print_calculation_times_directly(self):
    code = textwrap.dedent("""\
    nummer is 5
    nummertwee is 6
    print nummer * nummertwee""")

    result = hedy.transpile(code, self.level)

    expected = textwrap.dedent("""\
    nummer = '5'
    nummertwee = '6'
    print(str(int(nummer) * int(nummertwee)))""")

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

    self.assertEqual("30", self.run_code(result))

  def test_ask(self):
    result = hedy.transpile("antwoord is ask 'wat is je lievelingskleur?'", self.level)
    expected = "antwoord = input('wat is je lievelingskleur?')"
    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  def test_if_with_indent(self):
    code = textwrap.dedent("""\
    naam is Hedy
    if naam is Hedy:
        print 'koekoek'""")
    expected = textwrap.dedent("""\
    naam = 'Hedy'
    if str(naam) == str('Hedy'):
      print('koekoek')""")

    result = hedy.transpile(code, self.level)

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  def test_if_else(self):
    code = textwrap.dedent("""\
    antwoord is ask 'Hoeveel is 10 plus 10?'
    if antwoord is 20:
        print 'Goedzo!'
        print 'Het antwoord was inderdaad ' antwoord
    else:
        print 'Foutje'
        print 'Het antwoord moest zijn ' antwoord""")

    expected = textwrap.dedent("""\
    antwoord = input('Hoeveel is 10 plus 10?')
    if str(antwoord) == str('20'):
      print('Goedzo!')
      print('Het antwoord was inderdaad '+str(antwoord))
    else:
      print('Foutje')
      print('Het antwoord moest zijn '+str(antwoord))""")

    result = hedy.transpile(code, self.level)

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  def test_print_random(self):
    code = textwrap.dedent("""\
    keuzes is steen, schaar, papier
    computerkeuze is keuzes at random
    print 'computer koos ' computerkeuze""")
    expected = textwrap.dedent("""\
    keuzes = ['steen', 'schaar', 'papier']
    computerkeuze=random.choice(keuzes)
    print('computer koos '+str(computerkeuze))""")

    result = hedy.transpile(code, self.level)

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  def test_for_loop(self):
    code = textwrap.dedent("""\
    a is 2
    a is 3
    for a in range 2 to 4:
      a is a + 2
      b is b + 2""")
    expected = textwrap.dedent("""\
    a = '2'
    a = '3'
    step = 1 if int(2) < int(4) else -1
    for a in range(int(2), int(4) + step, step):
      a = int(a) + int(2)
      b = int(b) + int(2)""")

    result = hedy.transpile(code, self.level)

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)



  def test_if__else(self):
    code = textwrap.dedent("""\
    a is 5
    if a is 1:
      x is 2
    else:
      x is 222""")
    expected = textwrap.dedent("""\
    a = '5'
    if str(a) == str('1'):
      x = '2'
    else:
      x = '222'""")

    result = hedy.transpile(code, self.level)

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  def test_forloop(self):
    code = textwrap.dedent("""\
    for i in range 1 to 10:
      print i
    print 'wie niet weg is is gezien'""")
    expected = textwrap.dedent("""\
    step = 1 if int(1) < int(10) else -1
    for i in range(int(1), int(10) + step, step):
      print(str(i))
    print('wie niet weg is is gezien')""")
    result = hedy.transpile(code, self.level)

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  def test_for_nesting(self):
    code = textwrap.dedent("""\
    for i in range 1 to 3:
      for j in range 1 to 4:
        print 'rondje: ' i ' tel: ' j""")
    expected = textwrap.dedent("""\
    step = 1 if int(1) < int(3) else -1
    for i in range(int(1), int(3) + step, step):
      step = 1 if int(1) < int(4) else -1
      for j in range(int(1), int(4) + step, step):
        print('rondje: '+str(i)+' tel: '+str(j))""")

    result = hedy.transpile(code, self.level)

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  def test_if_nesting(self):
    code = textwrap.dedent("""\
    kleur is blauw
    kleurtwee is geel
    if kleur is blauw:
      if kleurtwee is geel:
        print 'Samen is dit groen!'""")
    expected = textwrap.dedent("""\
    kleur = 'blauw'
    kleurtwee = 'geel'
    if str(kleur) == str('blauw'):
      if str(kleurtwee) == str('geel'):
        print('Samen is dit groen!')""")

    result = hedy.transpile(code, self.level)

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)

  def test_if_under_else_in_for(self):
    code = textwrap.dedent("""\
    for i in range 0 to 10:
      antwoord is ask 'Wat is 5*5'
      if antwoord is 24:
        print 'Dat is fout!'
      else:
        print 'Dat is goed!'
      if antwoord is 25:
        i is 10""")

    expected = textwrap.dedent("""\
    step = 1 if int(0) < int(10) else -1
    for i in range(int(0), int(10) + step, step):
      antwoord = input('Wat is 5*5')
      if str(antwoord) == str('24'):
        print('Dat is fout!')
      else:
        print('Dat is goed!')
      if str(antwoord) == str('25'):
        i = '10'""")

    result = hedy.transpile(code, self.level)

    self.assertEqual(expected, result.code)
    self.assertEqual(False, result.has_turtle)
#programs with issues to see if we catch them properly
# (so this should fail, for now)
# at one point we want a real "Indent" error and a better error message
# for this!

  # def test_level_7_no_indentation(self):
  #   #test that we get a parse error here
  #   code = textwrap.dedent("""\
  #   antwoord is ask Hoeveel is 10 keer tien?
  #   if antwoord is 100
  #   print 'goed zo'
  #   else
  #   print 'bah slecht'""")
  #
  #   with self.assertRaises(Exception) as context:
  #     result = hedy.transpile(code, self.level)
  #   self.assertEqual(str(context.exception), 'Parse')


