const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deployer:", deployer.address);
  console.log("Balance:", (await ethers.provider.getBalance(deployer.address)).toString());

  const Factory = await ethers.getContractFactory("HealthProcurementAuctionFactory");
  const factory = await Factory.deploy();
  await factory.waitForDeployment();
  const factoryAddress = await factory.getAddress();
  console.log("Factory deployed at:", factoryAddress);

  const now = Math.floor(Date.now() / 1000);
  const auctionStart = now + 60;
  const biddingDeadline = now + 10 * 60;
  const revealDeadline = biddingDeadline + 10 * 60;
  const deliveryDeadline = revealDeadline + 30 * 60;
  const maxPrice = ethers.parseEther("0.01");

  const tx = await factory.createAuction(
    auctionStart,
    biddingDeadline,
    revealDeadline,
    deliveryDeadline,
    maxPrice
  );
  const receipt = await tx.wait();
  const event = receipt.logs.find((l) => l.fragment && l.fragment.name === "AuctionCreated");
  const auctionAddress = event.args.auction;
  console.log("Auction deployed at:", auctionAddress);

  console.log("\nVerify in block explorer:");
  console.log(`  npx hardhat verify --network sepolia ${factoryAddress}`);
  console.log(
    `  npx hardhat verify --network sepolia ${auctionAddress} ${deployer.address} ${auctionStart} ${biddingDeadline} ${revealDeadline} ${deliveryDeadline} ${maxPrice}`
  );
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
