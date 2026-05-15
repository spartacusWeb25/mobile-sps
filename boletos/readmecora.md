Emissão de boleto registrado
post
https://api.stage.cora.com.br/v2/invoices/

Gere um boleto registrado através desta API

154
Importante para Integração Direta
Para você conseguir efetuar essa integração é obrigatória a leitura sobre "Utilização das APIs" e recomendada a leitura sobre "Instruções Iniciais" e "Client Credentials e Client ID"
O que é um boleto registrado?
É um boleto que permite que a Cora saiba para quem a sua empresa está emitindo esta cobrança e com isso podemos acompanhar todo o ciclo de vida deste boleto.

Quem pode usar esta API?
Clientes Cora que estão cadastrados em Integração Direta ou Parceria Cora

Quais são requisitos para a utilização desta API?
Integração Direta: Ter finalizado a etapa de autorização

Parceria Cora: Já ter feito a etapa de autorização e autenticação

Escopo: para a modalidade Parceria Cora, é necessário ter ativado o escopo correto ao solicitar autorização e gerar token de acesso para que sua aplicação possa acessar e interagir com as informações da conta de forma segura e autorizada. É possível consultar mais detalhes sobre o escopo e autorização no tópico Redirecionamento.

Nome do escopo Descrição
invoice API de boleto
O que é possível configurar?
Juros: para cobrar após a data de vencimento
Multa: para cobrar após a data de vencimento
Desconto: aplicado até o dia anterior a data de vencimento
Notificação de cobrança: para lembrar o cliente sobre o pagamento
Bora pro código?
383
Parâmetros da requisição
Parâmetro Tipo Descrição
code
opcional
String Código definido por você, pode ser um id do recurso no seu sistema. Nós iremos retornar esse código sempre que você consultar uma fatura.
customer\
obrigatório
Customer Objeto Customer
services\
obrigatório
Lista de Services Lista de Objetos Services. Utilize este campo para descrever o que está sendo cobrado. Atenção: O nó services agrupa itens dentro de uma única invoice. Para emitir múltiplos boletos, realize chamadas separadas para o endpoint.
payment_terms\
obrigatório
PaymentTerms Objeto PaymentTerms
notification\
opcional
Notification Objeto Notification
Parâmetros da resposta
Parâmetro Tipo Descrição
id
obrigatório
String Identificador da fatura na Cora. Esse id poderá ser usado para consultar os detalhes da fatura.
status\
obrigatório
String Indica qual é o estado do boleto. Os status possíveis estão na Tabela de Estados dos Boletos.
created_at\
obrigatório
String Data de criação da fatura.
total_amount\
obrigatório
Int Valor total em centavos da fatura. Esse valor é a soma dos valores informados no parâmetro Services.
total_paid\
obrigatório
Int Valor total pago (em centavos), caso o boleto ainda não tenha sido pago, ele será zerado.
occurrence_date\
opcional
String Data que o cliente efetuou o pagamento do boleto junto ao banco.
code\
obrigatório
String Código definido por você, pode ser um id do recurso no seu sistema. Nós iremos retornar esse código sempre que você consultar uma fatura.
customer\
obrigatório
Customer Objeto Customer
services\
obrigatório
Lista de Services Lista de Objetos Services
payment_terms\
obrigatório
PaymentTerms Objeto PaymentTerms
payment_options\
obrigatório
PaymentOptions Objeto PaymentOptions
payments\
obrigatório
Payments Lista de Objetos Payments. Caso o pagamento ainda não tenha sido feito o array será vazio.
pix\
obrigatório
Pix Objeto Pix
Dicas de implementação
188
Premissas
Os parâmetros que tratam de valores são tipos primitivos inteiros com os centavos sendo representados pelos dois dígitos iniciais (unidade e dezena). Como exemplo, temos o valor de R$ 10,01 que é representado por 1001 dentro do valor total_amount. Veja o json abaixo:
JSON

{  
 "total_amount": 1001
}
Problemas conhecidos
Quando enviado um e-mail ou documentos inválidos a Cora está retornando erros genéricos ao invés de retornar erro 400 (Bad Request)
Erros Comuns
Código de erro

Descrição

401 (Unauthorized)

O token de acesso está inválido ou expirado. Erro comum no momento de trocas de ambientes (Stage/Production).

400 (Bad Request)

Requisição mal formatada. Alguns exemplos comuns:

Idempotency-Key que não está no formato correto (uuid)

Chave payment_term escrito no singular ao invés de payment_terms que é o correto.

Valor do boleto menor do que o mínimo de R$5 (amount: 500)

Campo valor (amount) mal formatado. Ex: 20,00 ao invés de 2000.- Data de vencimento do boleto anterior ao dia atual de emissão.

415 (Unsupported Media Type)

Falta do Content-Type application/json no header da requisição.

Tipos de Objetos
Objeto Customer
Parâmetro Tipo Descrição
name
obrigatório
String Nome do seu cliente (máximo 60 caracteres)
email\
opcional
String E-mail do seu cliente (máximo 60 caracteres)
document\
obrigatório
Document Objeto Document
address\
opcional
Address Objeto Address
Objeto Document
Parâmetro Tipo Descrição
identity
obrigatório
String Número do documento do seu cliente (apenas números, sem traços e pontos). Deve ser enviado como uma string.
type\
obrigatório
String Tipo de documento, os valores possíveis são "CPF" e "CNPJ". Caso não informado, iremos inferir pela quantidade de caracteres informado no parâmetro identity.
Objeto Address
Parâmetro Tipo Descrição
street
obrigatório
String Nome da rua do seu cliente.
number\
obrigatório
String Número da rua do seu cliente.
district\
obrigatório
String Bairro do seu cliente.
city\
obrigatório
String Cidade do seu cliente.
state\
obrigatório
String Estado do seu cliente no formato AA. Exemplos: SP, AC, GO, RJ.
complement\
obrigatório
String Complemento do endereço do seu cliente.
country\
opcional
String País do seu cliente.
zip_code\
obrigatório
String CEP do seu cliente. Formatos possíveis: 00111222 e 00111-222. O tamanho máximo de caracters é de 8.
Objeto Services
Parâmetro Tipo Descrição
name
obrigatório
String Nome do serviço prestado.
description\
obrigatório
String Descrição do serviço prestado. Máximo de 100 caracteres.
amount\
obrigatório
Int Valor do serviço prestado.
Objeto PaymentTerms
Parâmetro Tipo Descrição
due_date
obrigatório
String Data de vencimento do boleto. Deve seguir o formato AAAA-MM-DD.
fine\
opcional
Fine Objeto Fine
interest\
opcional
Interest Objeto Interest
discount\
opcional
Discount Objeto Discount
Objeto Fine
Parâmetro

Tipo

Descrição

date
opcional

String

Data a partir da qual será aplicada multa mensal. Essa data é facultativa, caso não informada, o padrão é data de vencimento +1.

amount\
opcional

Int

Valor em centavos da multa a ser cobrada.

Atenção
O parâmetro amount tem precedência sobre o parâmetro rate. Portanto, se for informado os dois parâmetros no objeto fine, apenas o atributo amount será considerado.

rate\
opcional

Double

Valor percentual da multa a ser cobrada.

Atenção
Esse parâmetro tem menor prioridade em relação ao parâmetro amount. Portanto, só será considerado caso o valor amount seja nulo. Valores possíveis: de 0 a 100 (com duas casas decimais).

Objeto Interest
Parâmetro Tipo Descrição
rate
obrigatório
Double Taxa de juros a ser cobrada. Valores possíveis: de 0 a 100 (com duas casas decimais).
Objeto Discount
Parâmetro Tipo Descrição
type
obrigatório
String Tipo de desconto aplicado. Valor fixo FIXED ou percentual PERCENT .
value\
obrigatório
Double Valor do desconto a ser aplicado. Apesar do campo ser Double, caso o tipo seja FIXED o valor decimal será truncado, mantendo o padrão de envio de valores fixos com centavos. Ex: R$ 20,50 é representado como 2050.
Objeto DiscountResponse
Parâmetro Tipo Descrição
percent
opcional
Double Valor definido no Objeto Discount como tipo PERCENT.
amount\
opcional
Int Valor definido no Objeto Discount como tipo FIXED.
Objeto Notification
Parâmetro Tipo Descrição
name
obrigatório
String Nome do contato para quem será enviada a notificação de cobrança (máximo 60 caracteres).
channels\
obrigatório
Lista de NotificationChannel Objeto NotificationChannel
Objeto NotificationChannel
Parâmetro

Tipo

Descrição

contact
obrigatório

String

Contato para qual será enviada a notificação de cobrança (máximo 60 caracteres). Deve ser um endereço de e-mail válido para notificações do tipo EMAIL (fulano@cora.com.br), e um número de telefone para notificações do tipo SMS (+5511999999999) - o código de pais +55 é obrigatório no envio da requisição

channel\
obrigatório

String

String que representa o canal de comunicação escolhido. Hoje o parâmetro aceita os canais "EMAIL" e "SMS".

Atenção
Notificações de cobrança via SMS fazem parte de uma funcionalidade do plano Cora Pro.

rules\
obrigatório

Lista de strings

Strings que representam as regras das notificações. As possíveis Strings estão detalhadas no Enum de Tipos de Notificação .

Objeto PaymentOptions
Parâmetro Tipo Descrição
bank_slip
obrigatório
BankSlip Objeto BankSlip
Objeto BankSlip
Parâmetro Tipo Descrição
barcode
obrigatório
String Código de barras do boleto.
digitable\
obrigatório
String Linha digitável do boleto. Número que deverá ser utilizado para pagamento.
registered\
obrigatório
String Informa se o boleto foi registrado ou não.
url\
obrigatório
String URL do PDF do boleto (os boletos são disponibilizados apenas em PDF, não há versão HTML).
our_number\
obrigatório
String Nosso número. Número do convênio concatenado com a sequência do documento.
Objeto Payments
Parâmetro

Tipo

Descrição

id
obrigatório

String

ID do pagamento atrelado Código de barras do boleto.

status\
obrigatório

String

Status do pagamento.

created_at\
obrigatório

String

Status do pagamento.

finalized_at\
obrigatório

String

Data do pagamento.

total_paid\
obrigatório

Int

Valor total pago em centavos.

method\
obrigatório

String

Método de pagamento.
"BANK_SLIP" indica pagamento realizado por código de barras. "PIX" indica pagamento via Pix.

interest\
obrigatório

Int

Valor total em centavos dos juros pagos.

fine\
obrigatório

Int

Valor total em centavos da multa paga.

Objeto PixResponse
Parâmetro Tipo Descrição
emv
obrigatório
String Quando um QR code é gerado esse campo virá preenchido. Código do Pix Copia e Cola, o mesmo que é utilizado para gerar o QR code.
Emitir um boleto com QR-code Pix
Objeto Payment_forms
Parâmetro Tipo Descrição
payment_forms
obrigatório
String Para criar um boleto com opção de pagamento por QR code basta inserir as duas opções de "BANK_SLIP" e "PIX".
Cancelamento
Ao realizar o pagamento pelo QR Code Pix, o boleto com código de barras é cancelado automaticamente em nossos sistemas e na Câmara Interbancária de Pagamentos, evitando assim o pagamento em duplicidade.

Importante
Para gerar um QR Code Pix no boleto é preciso que o cliente tenha cadastrada ao menos uma chave Pix.

Veja aqui como cadastrar uma chave Pix. Caso o cliente não tenha uma chave Pix cadastrada o boleto será gerado sem o QR code, apenas com o código de barras padrão.

Tipos de Enumeradores
Enum de Estados dos Boletos
Parâmetro Descrição
CANCELLED Boletos cancelados
DRAFT Boletos em rascunho, um estado intermediário entre criação e registro
IN_PAYMENT Boletos em processo de pagamento
LATE Boletos com pagamento em atraso, ou seja, após a data de vencimento
OPEN Boletos registrados, mas ainda não pagos
PAID Boletos que foram pagos com sucesso
Enum de Tipos de Notificação
Parâmetro Descrição
NOTIFY_FIFTEEN_DAYS_BEFORE_DUE_DATE Notifica quinze dias antes da data de vencimento.
NOTIFY_TEN_DAYS_BEFORE_DUE_DATE Notifica dez dias antes da data de vencimento.
NOTIFY_SEVEN_DAYS_BEFORE_DUE_DATE Notifica sete dias antes da data de vencimento.
NOTIFY_FIVE_DAYS_BEFORE_DUE_DATE Notifica cinco dias antes da data de vencimento.
NOTIFY_TWO_DAYS_BEFORE_DUE_DATE Notifica dois dias antes da data de vencimento.
NOTIFY_ON_DUE_DATE Notifica no dia do vencimento.
NOTIFY_TWO_DAYS_AFTER_DUE_DATE Notifica dois dias depois da data de vencimento.
NOTIFY_FIVE_DAYS_AFTER_DUE_DATE Notifica cinco dias depois da data de vencimento.
NOTIFY_SEVEN_DAYS_AFTER_DUE_DATE Notifica sete dias depois da data de vencimento.
NOTIFY_TEN_DAYS_AFTER_DUE_DATE Notifica dez dias depois da data de vencimento.
NOTIFY_FIFTEEN_DAYS_AFTER_DUE_DATE Notifica quinze dias depois da data de vencimento.
NOTIFY_WHEN_PAID Notifica quando o boleto é pago.
Integração Direta e Testes
Esta plataforma de documentação, atualmente, não permite o upload de informações importantes como certificados e private keys. Por isso, não recomendamos o uso dela para testes da modalidade de Integração Direta.

Para fazer os testes que incluam essas informações sensíveis pedimos que use um sistema de sua escolha.
Símbolo na cor rosa ao fundo com um pão de forma e ovo frito em cima
Opa, agora é hora do lanche!
Sim, finalizamos mais uma etapa de sua integração
Body Params
code
string
Defaults to meu_id
customer
object
required

customer object
services
array of objects
required
Objeto para descrição do serviço prestado ao pagador do boleto

ADD object
payment_terms
object
required

payment_terms object
notification
object
Objeto que representa a configuração das notificações de cobrança.

notification object
payment_forms
array of strings
Defaults to BANK_SLIP,PIX
Para criar um boleto com opção de pagamento por QR code é preciso inserir as opções de "BANK_SLIP" e "PIX".

string

string

ADD string
Headers
Idempotency-Key
string
required
Defaults to dd61d5b9-c9fb-4116-b5e0-1f8436993ac4
UUID aleatório gerado por você. Nós utilizamos esse header para evitar duplicidade de registros, ou seja, caso você não tenha recebido a resposta de alguma requisição e mandar o mesmo UUID, nós não duplicaremos o registro.

accept
string
enum
Defaults to application/json
Generated from available response content types

Allowed:

application/json

text/plain
Responses

200
200

400
400

401
401

415
415

Updated 3 months ago

Pagar boleto em stage

https://developers.cora.com.br/reference/pagar-boleto-em-stage
